"""Check every cst_* tool name referenced in a skill file against the live manifest."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "mcp_tools.json"

RE_SKILL = re.compile(r"cst_[a-z0-9_]+")

#: Identifiers that look like tools but are not tools, so their absence from the
#: manifest is expected. Keep this list short and justified.
NON_TOOL_IDENTIFIERS = {
    # CST's own Python modules, named in setup/import instructions
    "cst_interface": "CST Python module cst.interface",
    "cst_results": "CST Python module cst.results",
    "cst_mcp": "this server's own package name",
    # documented shapes of the import probe output, not tools
    "cst_interface_importable": "key printed by the import probe",
    "cst_results_importable": "key printed by the import probe",
    # placeholder in the "how to add your own tool" example
    "cst_my_tool": "placeholder in the extension example",
}


def main() -> int:
    if not MANIFEST.exists():
        print(f"FAIL: manifest missing: {MANIFEST}", file=sys.stderr)
        return 2
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = set()
    if isinstance(data, dict):
        for key in ("tools", "items", "entries"):
            if isinstance(data.get(key), list):
                for entry in data[key]:
                    if isinstance(entry, dict) and "name" in entry:
                        names.add(entry["name"])
    if not names:
        print("FAIL: could not extract tool names from manifest", file=sys.stderr)
        return 2

    targets = sys.argv[1:] or [
        str(ROOT / "skills" / "cst2026-simulation-execution" / "SKILL.md"),
        str(ROOT / "skills" / "cst-studio-suite-mcp" / "SKILL.md"),
    ]
    bad = 0
    for target in targets:
        path = Path(target)
        text = path.read_text(encoding="utf-8")
        found = sorted(set(RE_SKILL.findall(text)))
        unknown = [n for n in found
                   if n not in names and n not in NON_TOOL_IDENTIFIERS]
        excused = [n for n in found
                   if n not in names and n in NON_TOOL_IDENTIFIERS]
        suffix = "_tool"
        odd = [n for n in found if not n.endswith(suffix) and n not in NON_TOOL_IDENTIFIERS]
        print(f"\n=== {path.name} ===")
        print(f"referenced cst_* identifiers : {len(found)}")
        print(f"present in manifest          : {len(found) - len(unknown) - len(excused)}")
        if excused:
            print(f"known non-tool identifiers ({len(excused)}):")
            for n in sorted(excused):
                print(f"    = {n}  ({NON_TOOL_IDENTIFIERS[n]})")
        if odd:
            print(f"NOT ending in '_tool' ({len(odd)}): {odd}")
        if unknown:
            print(f"MISSING FROM MANIFEST ({len(unknown)}):")
            for n in unknown:
                print(f"    - {n}")
            bad += len(unknown)
        else:
            print("MISSING FROM MANIFEST (0): ok")

    print(f"\nmanifest tool count          : {len(names)}")
    print(f"total missing references     : {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
