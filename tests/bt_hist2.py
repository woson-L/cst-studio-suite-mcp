# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Read the v3 history: what did the two cuts actually record, and did they apply?"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
os.environ["CST_DESIGN_ENVIRONMENT_EXE"] = (
    r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe")
os.environ["CST_MCP_WORKSPACE"] = r"C:\CST_MCP_workspace"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_server  # noqa: E402,F401
from cst_mcp.session import session as S  # noqa: E402

REG = mcp_server.registry
PROJ = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919\base_pifa_v3.cst")
COPY = PROJ.with_name("hist_copy.cst")

REG.get("cst_quit_tool").handler()
if COPY.exists():
    COPY.unlink()
if COPY.with_suffix("").is_dir():
    shutil.rmtree(COPY.with_suffix(""))
shutil.copy2(PROJ, COPY)
shutil.copytree(PROJ.with_suffix(""), COPY.with_suffix(""))
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(COPY))

s = S()
hist = s.model3d()._GetHistory()
entries = hist["list"] if isinstance(hist, dict) else hist
print(f"history entries: {len(entries)}")
print("=" * 78)
for i, e in enumerate(entries, 1):
    if not isinstance(e, dict):
        continue
    name = e.get("name", "?")
    if any(k in name.lower() for k in ("brick", "subtract", "boolean", "port",
                                       "slice", "rebuild", "component", "rename",
                                       "change component", "change material")):
        print(f"\n--- {i}. {name}   (error={e.get('error')}, exclude={e.get('exclude')})")
        print("\n".join("    " + l for l in str(e.get("contents", "")).splitlines()))

print("\n" + "=" * 78)
print("current parameters as CST holds them")
print("=" * 78)
print(" ", json.dumps(s.list_parameters(), ensure_ascii=False))

print("\n" + "=" * 78)
print("parameters referenced by the cut bricks - do they resolve?")
print("=" * 78)
for name in ("gap_y", "fx", "fy"):
    try:
        v = s.parameter(name)
        print(f"  {name:<8} = {v!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {name:<8} read failed: {str(exc)[:80]}")

REG.get("cst_quit_tool").handler()
