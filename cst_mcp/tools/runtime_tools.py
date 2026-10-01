"""Runtime / toolbox command family.

Background
----------
The shipped `vendor/cst-runtime-cli` is incomplete: it contains only `devkit/`,
`skills/cst-runtime-cli/{references,tests,tools}`, `LICENSE` and the READMEs — the
`scripts/cst_runtime/` package that defines the 113 CLI commands is missing. The
original bridge pointed `RUNTIME_SCRIPT_ROOT` at that absent folder, so every
`cst_runtime_*` / `cst_toolbox_*` tool failed with

    cst-runtime-cli scripts not found: <...>\\skills\\cst-runtime-cli\\scripts

and `cst_toolbox_schema_catalog_tool` failed on the same root cause.

This module keeps those tool names but serves them from a built-in command
registry implemented directly on the CST session, so no external package and no
network access is required. Only implemented commands are advertised; anything
else raises with the list of available commands instead of failing silently.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Callable

from .. import config
from ..registry import ToolRegistry
from ..session import CSTError, session
from .result_tools import export_touchstone as _export_touchstone_impl
from .result_tools import model_audit

CATEGORY = "runtime"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
#: Kept for callers that still import it (the typed wrapper generator).
RUNTIME_SCRIPT_ROOT = (
    PROJECT_ROOT / "vendor" / "cst-runtime-cli" / "skills" / "cst-runtime-cli" / "scripts"
)
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("CST_RUNTIME_CLI_TIMEOUT", "120"))


class CSTRuntimeCLIError(RuntimeError):
    """A runtime command could not be executed."""


# ------------------------------------------------------------------ command impls
def _cmd_health_check(args: dict[str, Any]) -> dict[str, Any]:
    info = session().detect()
    ws = config.workspace()
    writable = True
    try:
        probe = ws / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception:  # noqa: BLE001
        writable = False
    info["workspace"] = str(ws)
    info["workspace_writable"] = writable
    return info


def _cmd_inspect_project(args: dict[str, Any]) -> dict[str, Any]:
    s = session()
    params = s.list_parameters()
    try:
        audit = model_audit()
    except Exception as exc:  # noqa: BLE001
        audit = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "project": s.info().get("active_project"),
        "parameters_count": len(params),
        "parameters": params,
        "model": audit,
    }


def _cmd_change_parameter(args: dict[str, Any]) -> dict[str, Any]:
    parameters = args.get("parameters")
    if parameters is None and args.get("name") is not None:
        parameters = {args["name"]: args.get("value")}
    if not isinstance(parameters, dict) or not parameters:
        raise CSTRuntimeCLIError("change-parameter needs {'parameters': {'name': value, ...}}")
    return session().set_parameters(parameters)


def _cmd_run_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return session().run_solver()


def _cmd_list_result_items(args: dict[str, Any]) -> dict[str, Any]:
    return session().list_results(cst_file=args.get("project_path"),
                                  module=args.get("module", "3d"))


def _cmd_get_1d_result(args: dict[str, Any]) -> dict[str, Any]:
    tree_path = args.get("tree_path") or args.get("path")
    if not tree_path:
        raise CSTRuntimeCLIError("get-1d-result needs 'tree_path'")
    return session().read_result(str(tree_path), cst_file=args.get("project_path"),
                                 module=args.get("module", "3d"),
                                 max_points=int(args.get("max_points", 2000)))


def _cmd_export_touchstone(args: dict[str, Any]) -> dict[str, Any]:
    filename = args.get("filename") or args.get("path")
    if not filename:
        raise CSTRuntimeCLIError("export-touchstone needs 'filename'")
    return _export_touchstone_impl(
        filename=str(filename),
        impedance=float(args.get("impedance", 50.0)),
        export_type=str(args.get("export_type", "S")),
        data_format=str(args.get("data_format", "RI")),
        frequency_range=str(args.get("frequency_range", "Full")),
    )


def _cmd_save_project(args: dict[str, Any]) -> dict[str, Any]:
    return session().save_project(path=args.get("project_path") or args.get("path"))


def _cmd_open_project(args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("project_path") or args.get("path")
    if not path:
        raise CSTRuntimeCLIError("cst-session-open needs 'project_path'")
    return session().open_project(str(path))


def _cmd_create_blank_project(args: dict[str, Any]) -> dict[str, Any]:
    return session().new_project(project_type=str(args.get("project_type", "mws")),
                                 path=args.get("project_path") or args.get("path"))


def _cmd_close_project(args: dict[str, Any]) -> dict[str, Any]:
    return session().close_project()


def _cmd_copy_project(args: dict[str, Any]) -> dict[str, Any]:
    source = args.get("source") or args.get("project_path")
    target = args.get("target")
    if not source or not target:
        raise CSTRuntimeCLIError("copy-project needs 'source' and 'target'")
    src = config.resolve_path(str(source))
    dst = config.resolve_path(str(target))
    if not src.is_file():
        raise CSTRuntimeCLIError(f"source project not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    src_dir, dst_dir = src.with_suffix(""), dst.with_suffix("")
    if src_dir.is_dir():
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
    return {"ok": True, "source": str(src), "target": str(dst)}


def _cmd_list_parameters(args: dict[str, Any]) -> dict[str, Any]:
    params = session().list_parameters()
    return {"ok": True, "count": len(params), "parameters": params}


def _cmd_run_vba(args: dict[str, Any]) -> dict[str, Any]:
    code = args.get("vba_code") or args.get("code")
    if not code:
        raise CSTRuntimeCLIError("run-vba needs 'vba_code'")
    return session().run_vba(str(code))


def _cmd_workspace(args: dict[str, Any]) -> dict[str, Any]:
    ws = config.workspace()
    ev = config.evidence_dir()
    return {
        "ok": True,
        "workspace": str(ws),
        "evidence_dir": str(ev),
        "projects": sorted(p.name for p in ws.glob("*.cst")),
        "evidence_files": sorted(p.name for p in ev.glob("*"))[:50],
    }


COMMANDS: dict[str, dict[str, Any]] = {
    "health-check": {
        "handler": _cmd_health_check, "category": "workspace",
        "summary": "CST install, Python libraries, workspace and running Design Environments.",
        "args": {},
    },
    "inspect-project": {
        "handler": _cmd_inspect_project, "category": "engineering",
        "summary": "Project info, all design parameters and a model audit in one call.",
        "args": {},
    },
    "change-parameter": {
        "handler": _cmd_change_parameter, "category": "engineering",
        "summary": "Set design parameters through the CST parameter list (no history edit).",
        "args": {"parameters": {"<name>": "<value>"}},
    },
    "run-simulation": {
        "handler": _cmd_run_simulation, "category": "simulation",
        "summary": "Run the configured solver and report CST's own diagnostics on failure.",
        "args": {},
    },
    "list-result-items": {
        "handler": _cmd_list_result_items, "category": "results",
        "summary": "List the 3D or schematic result tree.",
        "args": {"project_path": "optional .cst path", "module": "3d|schematic"},
    },
    "get-1d-result": {
        "handler": _cmd_get_1d_result, "category": "results",
        "summary": "Read one 1D result item.",
        "args": {"tree_path": "result tree path", "max_points": 2000},
    },
    "export-touchstone": {
        "handler": _cmd_export_touchstone, "category": "results",
        "summary": "Export S-parameters as Touchstone at a chosen reference impedance.",
        "args": {"filename": "target path without extension", "impedance": 50.0,
                 "data_format": "RI|MA|DB"},
    },
    "save-project": {
        "handler": _cmd_save_project, "category": "session",
        "summary": "Save the active project, optionally to a path.",
        "args": {"project_path": "optional target .cst path"},
    },
    "cst-session-open": {
        "handler": _cmd_open_project, "category": "session",
        "summary": "Open a .cst project in the Design Environment.",
        "args": {"project_path": ".cst path"},
    },
    "create-blank-project": {
        "handler": _cmd_create_blank_project, "category": "session",
        "summary": "Create a new project (mws default), saved into the workspace.",
        "args": {"project_path": "optional .cst path", "project_type": "mws"},
    },
    "cst-session-close": {
        "handler": _cmd_close_project, "category": "session",
        "summary": "Close the active project.",
        "args": {},
    },
    "copy-project": {
        "handler": _cmd_copy_project, "category": "workspace",
        "summary": "Copy a .cst file together with its companion folder.",
        "args": {"source": ".cst path", "target": ".cst path"},
    },
    "list-parameters": {
        "handler": _cmd_list_parameters, "category": "engineering",
        "summary": "Read every design parameter of the active project.",
        "args": {},
    },
    "run-vba": {
        "handler": _cmd_run_vba, "category": "engineering",
        "summary": "Execute raw CST VBA immediately (not recorded in the history tree).",
        "args": {"vba_code": "VBA source"},
    },
    "workspace": {
        "handler": _cmd_workspace, "category": "workspace",
        "summary": "Report the workspace and evidence folders and what they contain.",
        "args": {},
    },
}

PIPELINES: dict[str, dict[str, Any]] = {
    "inspect-project": {
        "summary": "Open a project and report parameters plus model state.",
        "steps": ["cst-session-open", "inspect-project"],
    },
    "prepare-experiment": {
        "summary": "Copy the working project, open the copy, apply new parameter values.",
        "steps": ["copy-project", "cst-session-open", "change-parameter", "save-project"],
    },
    "run-experiment": {
        "summary": "Solve the prepared project and export the S-parameters.",
        "steps": ["run-simulation", "export-touchstone", "list-result-items"],
    },
    "deliver-evidence": {
        "summary": "Save, export Touchstone and read the S-parameter item.",
        "steps": ["save-project", "export-touchstone", "get-1d-result"],
    },
}


# ---------------------------------------------------------------- public helpers
def detect_runtime() -> dict[str, Any]:
    return {
        "ok": True,
        "implementation": "built-in bridge (vendor scripts not required)",
        "vendored_runtime_scripts_present": RUNTIME_SCRIPT_ROOT.exists(),
        "vendored_runtime_script_root": str(RUNTIME_SCRIPT_ROOT),
        "command_count": len(COMMANDS),
        "commands": sorted(COMMANDS),
        "workspace": str(config.workspace()),
        "python_executable": __import__("sys").executable,
        "cst_install_root": str(config.cst_root()),
    }


def list_runtime_tools() -> dict[str, Any]:
    return {
        "ok": True,
        "count": len(COMMANDS),
        "tools": [
            {"name": name, "category": spec["category"],
             "summary": spec["summary"], "args": spec["args"]}
            for name, spec in sorted(COMMANDS.items())
        ],
    }


def list_runtime_pipelines() -> dict[str, Any]:
    return {"ok": True, "count": len(PIPELINES),
            "pipelines": [{"name": k, **v} for k, v in sorted(PIPELINES.items())]}


def runtime_usage_guide() -> dict[str, Any]:
    categories: dict[str, list[str]] = {}
    for name, spec in sorted(COMMANDS.items()):
        categories.setdefault(spec["category"], []).append(name)
    return {
        "ok": True,
        "workflow": [
            "1. health-check - confirm CST and the workspace before anything else.",
            "2. cst-session-open or create-blank-project - get a project active.",
            "3. inspect-project - read the real parameter names and model state.",
            "4. copy-project + change-parameter - change a design point on a copy.",
            "5. run-simulation - solve; then list-result-items.",
            "6. export-touchstone + get-1d-result - produce evidence.",
            "7. save-project - persist the working project.",
        ],
        "categories": categories,
        "notes": [
            "Parameters change only through change-parameter (the CST parameter list).",
            "Never put StoreParameter/StoreParameters/Rebuild in a history block: CST refuses it "
            "('The rebuild operation cannot be used inside a structure macro.') and can block the session.",
        ],
    }


def _resolve(name: str) -> dict[str, Any]:
    key = (name or "").strip()
    if not key:
        raise CSTRuntimeCLIError("tool_name must not be empty")
    if key in COMMANDS:
        return COMMANDS[key]
    raise CSTRuntimeCLIError(
        f"unknown CST runtime command {key!r}. Available commands: {', '.join(sorted(COMMANDS))}"
    )


def describe_runtime_tool(tool_name: str) -> dict[str, Any]:
    spec = _resolve(tool_name)
    return {"ok": True, "name": tool_name.strip(), "category": spec["category"],
            "summary": spec["summary"], "args_schema": spec["args"], "implemented": True}


def runtime_args_template(tool_name: str) -> dict[str, Any]:
    spec = _resolve(tool_name)
    template: dict[str, Any] = {}
    for key, hint in spec["args"].items():
        if isinstance(hint, dict):
            template[key] = hint
        elif "optional" in str(hint):
            template[key] = None
        elif "|" in str(hint):
            template[key] = str(hint).split("|")[0].strip()
        elif str(hint).replace(".", "", 1).isdigit():
            template[key] = float(hint) if "." in str(hint) else int(hint)
        elif "mws" in str(hint):
            template[key] = "mws"
        else:
            template[key] = f"<{hint}>"
    return {"ok": True, "tool": tool_name.strip(), "args": template}


def invoke_runtime_tool(tool_name: str, args: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    spec = _resolve(tool_name)
    try:
        data = spec["handler"](dict(args or {}))
    except CSTRuntimeCLIError:
        raise
    except CSTError:
        raise
    except Exception as exc:  # noqa: BLE001
        tail = []
        try:
            tail = [m["text"] for m in session().messages(limit=6)]
        except Exception:  # noqa: BLE001
            pass
        detail = f"{type(exc).__name__}: {exc}"
        if tail:
            detail += " | CST messages: " + " / ".join(tail[-3:])
        raise CSTRuntimeCLIError(detail) from exc
    result: dict[str, Any] = {"ok": True, "status": "success", "tool": tool_name.strip()}
    if isinstance(data, dict):
        result.update(data)
    else:
        result["result"] = data
    return result


def load_runtime_schema_catalog(category: str | None = None) -> dict[str, Any]:
    """Command catalog used by the typed wrapper generator."""
    tools: dict[str, Any] = {}
    for name, spec in sorted(COMMANDS.items()):
        if category and spec["category"] != category:
            continue
        properties: dict[str, Any] = {}
        required: list[str] = []
        for key, hint in spec["args"].items():
            if isinstance(hint, dict):
                properties[key] = {"type": "object", "default": hint}
                continue
            text = str(hint)
            prop: dict[str, Any] = {"type": "string"}
            if "optional" in text:
                prop["type"] = ["string", "null"]
            elif "|" in text:
                prop["enum"] = [p.strip() for p in text.split("|")]
            elif text.replace(".", "", 1).isdigit():
                prop = {"type": "number" if "." in text else "integer",
                        "default": float(text) if "." in text else int(text)}
            properties[key] = prop
            if "optional" not in text:
                required.append(key)
        schema: dict[str, Any] = {"$schema": "http://json-schema.org/draft-07/schema#",
                                  "title": f"{name}Arguments", "type": "object",
                                  "properties": properties, "additionalProperties": False}
        if required:
            schema["required"] = required
        tools[name] = {
            "name": name,
            "function_name": _py_name(name),
            "category": spec["category"],
            "risk": "low",
            "description": spec["summary"],
            "json_schema": schema,
            "args_template": runtime_args_template(name)["args"],
        }
    return {"ok": True, "count": len(tools), "tools": tools}


def _py_name(name: str) -> str:
    import keyword

    chars = [c if (c.isalnum() or c == "_") else "_" for c in name.replace("-", "_")]
    out = "".join(chars).strip("_") or "tool"
    if out[0].isdigit():
        out = f"tool_{out}"
    if keyword.iskeyword(out):
        out = f"{out}_"
    return out


# ------------------------------------------------------------------- tool family
def register_tools(registry: ToolRegistry) -> None:
    @registry.tool(
        "cst_runtime_detect_tool", "Report the built-in runtime command bridge and its commands.",
        CATEGORY, params={}, returns="{ok, command_count, commands}",
        notes=["Works without the vendored cst-runtime-cli scripts."],
    )
    def runtime_detect() -> dict[str, Any]:
        return detect_runtime()

    @registry.tool(
        "cst_runtime_list_tools_tool", "List the runtime commands available through this MCP server.",
        CATEGORY, params={}, returns="{count, tools}",
    )
    def runtime_list() -> dict[str, Any]:
        return list_runtime_tools()

    @registry.tool(
        "cst_runtime_describe_tool", "Describe one runtime command.",
        CATEGORY, params={"tool_name": "str"}, required=["tool_name"],
    )
    def runtime_describe(tool_name: str) -> dict[str, Any]:
        return describe_runtime_tool(tool_name)

    @registry.tool(
        "cst_runtime_args_template_tool", "Return an argument template for one runtime command.",
        CATEGORY, params={"tool_name": "str"}, required=["tool_name"],
    )
    def runtime_template(tool_name: str) -> dict[str, Any]:
        return runtime_args_template(tool_name)

    @registry.tool(
        "cst_runtime_invoke_tool", "Invoke a runtime command by name with JSON arguments.",
        CATEGORY,
        params={"tool_name": "str", "args": "dict"},
        required=["tool_name"],
        examples=[{"tool_name": "health-check"},
                  {"tool_name": "get-1d-result",
                   "args": {"tree_path": "1D Results\\S-Parameters\\S1,1"}}],
        notes=["Run cst_runtime_list_tools_tool to see the command names."],
    )
    def runtime_invoke(tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return invoke_runtime_tool(tool_name, args)

    @registry.tool(
        "cst_runtime_list_pipelines_tool", "List the runtime workflow recipes.",
        CATEGORY, params={}, returns="{count, pipelines}",
    )
    def runtime_pipelines() -> dict[str, Any]:
        return list_runtime_pipelines()

    @registry.tool(
        "cst_runtime_usage_guide_tool", "Return the machine-readable usage guide for the runtime family.",
        CATEGORY, params={},
    )
    def runtime_guide() -> dict[str, Any]:
        return runtime_usage_guide()

    # short aliases without the word "runtime"
    @registry.tool(
        "cst_toolbox_detect_tool", "Alias of cst_runtime_detect_tool.",
        CATEGORY, params={},
    )
    def toolbox_detect() -> dict[str, Any]:
        return detect_runtime()

    @registry.tool(
        "cst_toolbox_list_tools_tool", "Alias of cst_runtime_list_tools_tool.",
        CATEGORY, params={},
    )
    def toolbox_list() -> dict[str, Any]:
        return list_runtime_tools()

    @registry.tool(
        "cst_toolbox_describe_tool", "Alias of cst_runtime_describe_tool.",
        CATEGORY, params={"tool_name": "str"}, required=["tool_name"],
    )
    def toolbox_describe(tool_name: str) -> dict[str, Any]:
        return describe_runtime_tool(tool_name)

    @registry.tool(
        "cst_toolbox_args_template_tool", "Alias of cst_runtime_args_template_tool.",
        CATEGORY, params={"tool_name": "str"}, required=["tool_name"],
    )
    def toolbox_template(tool_name: str) -> dict[str, Any]:
        return runtime_args_template(tool_name)

    @registry.tool(
        "cst_toolbox_invoke_tool", "Alias of cst_runtime_invoke_tool.",
        CATEGORY,
        params={"tool_name": "str", "args": "dict"},
        required=["tool_name"],
    )
    def toolbox_invoke(tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return invoke_runtime_tool(tool_name, args)

    @registry.tool(
        "cst_toolbox_list_pipelines_tool", "Alias of cst_runtime_list_pipelines_tool.",
        CATEGORY, params={},
    )
    def toolbox_pipelines() -> dict[str, Any]:
        return list_runtime_pipelines()

    @registry.tool(
        "cst_toolbox_usage_guide_tool", "Alias of cst_runtime_usage_guide_tool.",
        CATEGORY, params={},
    )
    def toolbox_guide() -> dict[str, Any]:
        return runtime_usage_guide()

    @registry.tool(
        "cst_toolbox_schema_catalog_tool", "Return the JSON-schema catalog of the runtime commands.",
        CATEGORY, params={"category": "str | null"}, returns="{count, tools}",
    )
    def schema_catalog(category: str | None = None) -> dict[str, Any]:
        return load_runtime_schema_catalog(category=category)

    @registry.tool(
        "cst_toolbox_generate_typed_wrappers_tool",
        "Generate typed Python wrappers for the runtime commands into a file.",
        CATEGORY,
        params={"output_path": "str | null", "category": "str | null"},
        returns="{ok, output_path, tool_count, functions}",
    )
    def generate_wrappers(output_path: str | None = None,
                           category: str | None = None) -> dict[str, Any]:
        catalog = load_runtime_schema_catalog(category=category)
        records = catalog["tools"]
        # Default into the workspace, not the (possibly read-only) install folder.
        target = (config.resolve_path(output_path) if output_path
                  else config.workspace() / "generated" / "cst_toolbox_wrappers.py")
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            '"""Generated typed wrappers for the CST MCP runtime commands.',
            "",
            "Do not edit by hand; regenerate with cst_toolbox_generate_typed_wrappers_tool.",
            '"""',
            "from __future__ import annotations",
            "",
            "from typing import Any",
            "",
            "from cst_mcp.tools.runtime_tools import invoke_runtime_tool",
            "",
        ]
        for name, record in records.items():
            schema = record["json_schema"]
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            params = []
            for field, prop in props.items():
                py = _py_name(field)
                ptype = {"string": "str", "number": "float", "integer": "int",
                         "boolean": "bool", "object": "dict[str, Any]",
                         "array": "list[Any]"}.get(
                             prop.get("type") if isinstance(prop.get("type"), str) else "string",
                             "Any")
                if field in required:
                    params.append(f"{py}: {ptype}")
                else:
                    default = repr(prop["default"]) if "default" in prop else "None"
                    params.append(f"{py}: {ptype} | None = {default}")
            signature = ", ".join(params + ["**extra: Any"])
            lines.append(f"def {record['function_name']}(*, {signature}) -> dict[str, Any]:")
            lines.append(f'    """{record["description"]}"""')
            lines.append("    args: dict[str, Any] = {}")
            for field in props:
                py = _py_name(field)
                if field in required:
                    lines.append(f"    args[{field!r}] = {py}")
                else:
                    lines.append(f"    if {py} is not None:")
                    lines.append(f"        args[{field!r}] = {py}")
            lines.append("    args.update(extra)")
            lines.append(f"    return invoke_runtime_tool({name!r}, args)")
            lines.append("")
            lines.append("")
        target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return {"ok": True, "output_path": str(target), "tool_count": len(records),
                "functions": [r["function_name"] for r in records.values()]}
