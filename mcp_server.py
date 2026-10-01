"""CST Studio Suite MCP server.

Drives CST Studio Suite 2026 through its official automation API: modelling,
materials, ports, boundaries, mesh, solver selection, frequency range, monitors,
solver runs, result reading and evidence export.

Design notes
------------
* Tools are declared in `cst_mcp/tools/*.py` and registered into a registry, so
  the surface can grow without touching this file. Drop a new module with a
  `register_tools(registry)` hook into that folder and it is picked up.
* The machine-readable tool manifest is generated from the same registry, so the
  documentation can never drift from the implementation.
* Parameters are changed through the CST parameter list, never inside a history
  block: CST 2026 refuses the latter and can block the Design Environment.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from cst_mcp import config
from cst_mcp.registry import ToolRegistry
from cst_mcp.session import CSTError, dumps, session

INSTRUCTIONS = """You are controlling CST Studio Suite 2026 through MCP.

How to work
-----------
1. cst_health_check_tool first: confirm CST, the Python libraries and the workspace.
2. cst_connect_tool then cst_new_project_tool (or cst_open_project_tool). A new project is
   saved into the workspace automatically.
3. cst_get_parameters_tool to see the real parameter names before touching anything.
4. Build the model with cst_add_to_history_tool or the typed cst_create_* tools. One named
   block per step keeps the CST history tree readable.
5. cst_set_solver_tool to choose the solver, then cst_set_frequency_range_tool for the band,
   then cst_configure_fd_solver_tool / cst_configure_td_solver_tool for accuracy and mesh.
6. cst_set_boundary_tool, cst_set_mesh_tool, cst_add_monitor_tool as needed.
7. cst_save_project_tool, then cst_run_solver_tool.
8. cst_list_results_tool, cst_read_result_tool, cst_export_touchstone_tool.

Rules that prevent broken or fake results
-----------------------------------------
* Change parameters ONLY with cst_set_parameters_tool. Never put StoreParameter,
  StoreParameters or Rebuild inside cst_add_to_history_tool: CST 2026 refuses it
  ("The rebuild operation cannot be used inside a structure macro.") and can leave the
  Design Environment unresponsive.
* Save before solving. A solver run without a frequency range fails with
  "Solver run failed. Frequency range not set correctly."
* After every solve, check cst_read_result_tool on
  "1D Results\\Reference Impedance\\ZRef 1(1)" and, for waveguide ports,
  "1D Results\\Port Information\\Cutoff Frequency\\1(1)". A solver can succeed and still
  produce meaningless S-parameters if the port mode is evanescent or the reference
  impedance is not what you think.
* Convert S-parameters yourself: dB = 20*log10(abs(S)). Do not report Abs(E) as gain.
* Report the numbers from exported files, not from a screenshot.
"""

mcp = FastMCP("cst-studio-suite-mcp", instructions=INSTRUCTIONS)

registry = ToolRegistry()


def _register_manifest_tools() -> None:
    """Tools that describe the server's own surface (for agents and for humans)."""

    @registry.tool(
        "cst_list_mcp_tools_tool",
        "List every CST MCP tool with its category, summary and parameters.",
        "meta",
        params={"category": "str | null"},
        returns="{count, categories, tools}",
        notes=["Use this to discover the surface instead of guessing tool names."],
    )
    def list_mcp_tools(category: str | None = None) -> dict[str, Any]:
        specs = registry.all()
        if category:
            specs = [s for s in specs if s.category == category]
        grouped = registry.by_category()
        return {
            "ok": True,
            "count": len(specs),
            "categories": {name: len(items) for name, items in sorted(grouped.items())},
            "tools": [s.to_manifest() for s in specs],
        }

    @registry.tool(
        "cst_tool_manifest_tool",
        "Return the full machine-readable manifest of the CST MCP (write it to a file with out_path).",
        "meta",
        params={"out_path": "str | null"},
        returns="the manifest object, and the file path when out_path is given",
        notes=["Another agent can read this JSON to learn the whole tool surface and the workflow."],
    )
    def tool_manifest(out_path: str | None = None) -> dict[str, Any]:
        manifest = build_manifest()
        if out_path:
            target = config.resolve_path(out_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "out_path": str(target), "tool_count": manifest["tool_count"]}
        return manifest

    @registry.tool(
        "cst_call_tool",
        "Call any registered CST MCP tool by name through the registry (dynamic dispatch).",
        "meta",
        params={"tool_name": "str", "args": "dict"},
        required=["tool_name"],
        returns="the wrapped tool's result",
        notes=[
            "Exists so a new tool can be added without reconnecting the MCP client.",
            "Prefer calling the tool directly when it is already exposed as an MCP tool.",
        ],
    )
    def call_tool(tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        spec = registry.get(tool_name)
        return spec.handler(**(args or {}))


def build_manifest() -> dict[str, Any]:
    grouped = registry.by_category()
    return {
        "name": "cst-studio-suite-mcp",
        "version": "2.0.0",
        "target_software": "CST Studio Suite 2026 (verified on 2026.2)",
        "transport": "stdio",
        "tool_count": len(registry),
        "categories": [
            {"name": name, "tool_count": len(items), "tools": [t.name for t in items]}
            for name, items in sorted(grouped.items())
        ],
        "tools": [spec.to_manifest() for spec in registry.all()],
        "conventions": {
            "naming": "cst_<verb>_<object>_tool",
            "solid_names": "component:solid, e.g. 'antenna:patch'",
            "units": "millimetres and GHz unless the project says otherwise",
            "parameters": "change with cst_set_parameters_tool only",
            "history_blocks": "never contain StoreParameter/StoreParameters/Rebuild",
            "s_parameters": "dB = 20*log10(abs(S))",
            "evidence": "read numbers from exported files, not from the screen",
        },
        "workflow": workflow(),
        "configuration": {
            "env_file": ".env next to mcp_server.py",
            "keys": ["CST_INSTALL_ROOT", "CST_DESIGN_ENVIRONMENT_EXE",
                     "CST_MCP_WORKSPACE", "CST_MCP_EVIDENCE"],
            # The values are resolved from .env at run time and are deliberately not
            # baked in here: this manifest is committed, and one machine's absolute
            # paths must not travel with it. Read the live values with
            # cst_workspace_tool or cst_health_check_tool.
            "resolved_at": "run time, from .env",
        },
        "extensions": {
            "how_to_add_a_tool": [
                "Create cst_mcp/tools/<your_module>.py",
                "Define register_tools(registry) and call registry.tool(...) or registry.add(...)",
                "Restart the MCP server: the module is discovered automatically",
            ],
            "hook": "register_tools(registry)",
            "discovered": EXTENSION_REPORT,
        },
    }


def workflow() -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "environment",
         "tools": ["cst_health_check_tool", "cst_detect_tool", "cst_connect_tool"],
         "goal": "know that CST and the Python libraries are usable"},
        {"step": 2, "name": "project",
         "tools": ["cst_new_project_tool", "cst_open_project_tool", "cst_save_project_tool",
                   "cst_project_info_tool"],
         "goal": "have one saved project in the workspace"},
        {"step": 3, "name": "parameters",
         "tools": ["cst_get_parameters_tool", "cst_set_parameters_tool"],
         "goal": "know the parameter names and change values safely"},
        {"step": 4, "name": "model",
         "tools": ["cst_create_brick_tool", "cst_create_cylinder_tool", "cst_boolean_tool",
                   "cst_transform_tool", "cst_assign_material_tool", "cst_add_to_history_tool"],
         "goal": "geometry and materials as named, replayable history blocks"},
        {"step": 5, "name": "ports",
         "tools": ["cst_add_waveguide_port_tool", "cst_add_discrete_port_tool",
                   "cst_list_ports_tool"],
         "goal": "a port whose mode propagates in the band and whose reference impedance is intended"},
        {"step": 6, "name": "solver",
         "tools": ["cst_set_solver_tool", "cst_set_frequency_range_tool",
                   "cst_configure_fd_solver_tool", "cst_configure_td_solver_tool",
                   "cst_configure_eigenmode_solver_tool", "cst_get_solver_tool"],
         "goal": "the right solver, the right band, the right accuracy"},
        {"step": 7, "name": "domain",
         "tools": ["cst_set_boundary_tool", "cst_set_symmetry_tool", "cst_set_background_tool",
                   "cst_set_mesh_tool", "cst_generate_mesh_tool", "cst_add_monitor_tool"],
         "goal": "a meshable, radiating model with the monitors you will need"},
        {"step": 8, "name": "solve",
         "tools": ["cst_save_project_tool", "cst_run_solver_tool", "cst_messages_tool"],
         "goal": "a completed solve, or a CST error message that says why not"},
        {"step": 9, "name": "verify",
         "tools": ["cst_list_results_tool", "cst_read_result_tool", "cst_read_reference_impedance_tool",
                   "cst_read_port_info_tool", "cst_model_audit_tool"],
         "goal": "prove the result is physically meaningful, not just present"},
        {"step": 10, "name": "evidence",
         "tools": ["cst_export_touchstone_tool", "cst_export_ascii_tool", "cst_save_project_tool"],
         "goal": "files another tool or person can re-check"},
        {"step": 11, "name": "parameter study (optional)",
         "tools": ["cst_sweep_preview_tool", "cst_sweep_run_tool"],
         "goal": "one copied project per case with the swept parameters applied; preview first, "
                 "and only then decide whether to solve"},
        {"step": 12, "name": "release",
         "tools": ["cst_quit_tool"],
         "goal": "close every project and release the Design Environment, so the next job starts "
                 "with full memory"},
    ]


EXTENSION_REPORT: dict[str, Any] = {}


def bootstrap() -> None:
    global EXTENSION_REPORT
    _register_manifest_tools()
    EXTENSION_REPORT = registry.discover_extensions()
    for spec in registry.all():
        mcp.add_tool(spec.handler, name=spec.name, description=spec.summary)


bootstrap()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
