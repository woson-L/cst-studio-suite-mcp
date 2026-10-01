# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Dump the raw CST history tree and the boolean tool's emitted VBA.

Read-only: opens the project, reads VBA, writes nothing to the model.
"""
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
PROJ = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919\base_pifa_v2.cst")
COPY = PROJ.with_name("diag_copy.cst")

print("=" * 78)
print("A. what VBA does cst_boolean_tool emit?")
print("=" * 78)
# Ask the geometry builder directly, without CST, by importing the module.
import cst_mcp.vba.geometry as G  # noqa: E402

for name in ("boolean", "subtract", "boolean_block", "bool_op"):
    fn = getattr(G, name, None)
    if fn:
        print(f"  found builder: {name}")
try:
    import inspect
    src = inspect.getsource(G)
    i = src.find("def ")
    for fn_name in ("boolean", "unite", "subtract"):
        j = src.find(f"def {fn_name}(")
        if j >= 0:
            print(f"\n  --- {fn_name} ---")
            print("\n".join("    " + l for l in src[j:j + 900].splitlines()[:28]))
except Exception as exc:  # noqa: BLE001
    print("  introspection failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("B. raw history tree of the project")
print("=" * 78)
if COPY.exists():
    COPY.unlink()
if COPY.with_suffix("").is_dir():
    shutil.rmtree(COPY.with_suffix(""))
shutil.copy2(PROJ, COPY)
shutil.copytree(PROJ.with_suffix(""), COPY.with_suffix(""))

REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(COPY))
s = S()

# python-side history access (the .pyd exposes _GetHistory on the modeler)
try:
    m = s.model3d()
    n = m._GetHistory()
    print(f"  _GetHistory() = {n}")
    for i in range(1, int(n) + 1):
        try:
            print(f"    {i:>2}. {m.GetHistoryName(i)}")
        except Exception as exc:  # noqa: BLE001
            print(f"    {i:>2}. <name read failed: {str(exc)[:60]}>")
except Exception as exc:  # noqa: BLE001
    print("  python history read failed:", str(exc)[:250])

print("\n" + "=" * 78)
print("C. component / solid inventory straight from CST")
print("=" * 78)
try:
    comps = s.run_vba('Sub Main\nDim t As String, i As Long, n As Long\n'
                      'On Error Resume Next\nn = Component.GetNumberOfComponents()\n'
                      'For i = 0 To n - 1\n'
                      't = t & Component.GetNameFromIndex(i) & vbLf\nNext i\n'
                      'On Error GoTo 0\nReportInformationToWindow "C=" & t\nEnd Sub\n')
    for msg in reversed(s.messages(limit=12)):
        if msg["text"].startswith("C="):
            print("  components:")
            for line in msg["text"][2:].splitlines():
                if line.strip():
                    print("   ", line.strip())
            break
except Exception as exc:  # noqa: BLE001
    print("  failed:", str(exc)[:200])

REG.get("cst_quit_tool").handler()
