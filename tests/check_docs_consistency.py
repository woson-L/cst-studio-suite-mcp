"""Gate: every tool named in the docs must exist, must not be a known-broken stub,
and any example arguments shown for it must be real parameters.

This exists because a documentation drift went unnoticed: SKILL.md told the model to
call `cst_generate_mesh_tool`, a tool that can never succeed, and README described
tool behaviour that had already changed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mcp_server  # noqa: E402,F401  - bootstrap registers the tools

REG = mcp_server.registry
BY_NAME = {spec.name: spec for spec in REG.all()}

DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "start" / "install.md",
    ROOT / "docs" / "use" / "quickstart.md",
    ROOT / "docs" / "extend" / "overview.md",
    ROOT / "docs" / "extend" / "add-a-tool-family.md",
    ROOT / "skills" / "cst-studio-suite-mcp" / "SKILL.md",
    ROOT / "skills" / "cst2026-simulation-execution" / "SKILL.md",
]

#: Tools that exist for documentation/guard purposes and are expected to raise.
#: Naming one of these as part of a working sequence is the bug this gate catches.
KNOWN_NON_WORKING = {
    "cst_generate_mesh_tool": "always raises: CST has no standalone mesh-generation VBA command",
}

#: Identifiers that look like tools but are not.
NOT_TOOLS = {
    "cst_interface": "CST Python module",
    "cst_results": "CST Python module",
    "cst_mcp": "this package",
    "cst_interface_importable": "probe output key",
    "cst_results_importable": "probe output key",
    "cst_my_tool": "placeholder in the extension example",
    "cst_my_operation_tool": "placeholder in the extension example",
    "cst_runtime_cli": "external CLI",
    "cst_runtime_cli_bridge": "module name",
    "cst_runtime": "module path fragment",
    "cst_automation": "prose, not a tool",
    "cst_exe_exists": "health-check output key",
    # top-level helper modules of the parameter-sweep family (imported by
    # cst_mcp/tools/sweep_tools.py; they are modules, not tools)
    "cst_parameter_sweep": "module name (sweep family)",
    "cst_schematic": "module name (sweep family)",
    "cst_typed_wrapper_generator": "module name from the previous package",
}

#: Documentation writes tool families as `cst_runtime_*` or `cst_create_*`. A
#: trailing underscore (or the name being a strict prefix of several real tools)
#: means it is a family pattern, not a tool name.
RE_FAMILY = re.compile(r"^cst_[a-z0-9_]*_$")


def _is_family_pattern(name: str) -> bool:
    if RE_FAMILY.match(name):
        return True
    matches = [t for t in BY_NAME if t.startswith(name)]
    return len(matches) >= 2

RE_IDENT = re.compile(r"\bcst_[a-z0-9_]+\b")

problems: list[str] = []
notes: list[str] = []


def _example_blocks(text: str):
    """Yield (tool_name, inner_text) for each `cst_x_tool {...}` with balanced braces.

    Regex alone is not enough: a non-greedy `{.*?}` stops at the first inner `}`, and
    a greedy one runs into the next tool call, both of which produce false positives.
    """
    for m in re.finditer(r"\b(cst_[a-z0-9_]+_tool)\s*\{", text):
        depth = 0
        start = m.end() - 1
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield m.group(1), text[start + 1:i]
                    break


def _top_level_keys(inner: str) -> list[str]:
    """Keys at brace depth 0 of an argument object."""
    keys, depth = [], 0
    for km in re.finditer(r'[{}\n]|"([A-Za-z_][A-Za-z0-9_]*)"\s*:', inner):
        token = km.group(0)
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif km.group(1) and depth == 0:
            keys.append(km.group(1))
    return keys


def main() -> int:
    print(f"registry: {len(BY_NAME)} tools")
    for doc in DOCS:
        if not doc.is_file():
            problems.append(f"{doc.name}: documented file is missing")
            continue
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(ROOT)
        names = sorted(set(RE_IDENT.findall(text)))

        unknown = [n for n in names
                   if n not in BY_NAME and n not in NOT_TOOLS
                   and not _is_family_pattern(n)]
        if unknown:
            problems.append(f"{rel}: names unknown tools: {unknown}")

        # A non-working stub must never appear as a call to make. It is allowed to
        # appear when the surrounding text warns about it.
        for stub, reason in KNOWN_NON_WORKING.items():
            for m in re.finditer(rf"^{{?{stub}\b", text, re.MULTILINE):
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.start())
                line = text[line_start:line_end if line_end > 0 else len(text)]
                # context: 3 lines above
                ctx_start = text.rfind("\n", 0, max(0, line_start - 1))
                ctx_start = text.rfind("\n", 0, max(0, ctx_start - 1))
                context = text[max(0, ctx_start):line_end].lower()
                if not any(w in context for w in
                           ("raise", "not exposed", "no separate", "always raises",
                            "cannot", "不存在", "没有", "不可用", "报错")):
                    problems.append(
                        f"{rel}: line {text[:m.start()].count(chr(10)) + 1} uses "
                        f"{stub} as a working call ({reason}). Line: {line.strip()[:90]}"
                    )

        # Example argument blocks: cst_x_tool {...} — top-level keys must be real
        # parameters. Keys inside a nested object (e.g. "parameters": {"Lg": 60}) are
        # user data, not parameters.
        for tool, inner in _example_blocks(text):
            spec = BY_NAME.get(tool)
            if spec is None:
                continue  # already reported as unknown
            keys = _top_level_keys(inner)
            if not keys:
                continue
            declared = set(spec.params or {})
            bad = sorted({k for k in keys if k not in declared})
            if bad:
                problems.append(
                    f"{rel}: {tool} example passes undeclared parameter(s) {bad}; "
                    f"declared: {sorted(declared)}"
                )

    # every tool must still be discoverable from the manifest docs
    manifest = ROOT / "docs" / "mcp_tools.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("tool_count") != len(BY_NAME):
            problems.append(
                f"docs/mcp_tools.json says {data.get('tool_count')} tools, registry has {len(BY_NAME)}"
            )
    else:
        problems.append("docs/mcp_tools.json missing")

    print(f"documents checked: {len(DOCS)}")
    for note in notes:
        print("  [info]", note)
    if problems:
        print(f"\nPROBLEMS ({len(problems)}):")
        for p in problems:
            print("  [FAIL]", p)
    else:
        print("  [ ok ] every documented tool name, stub usage and example parameter is valid")
    print(f"\nproblems found: {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
