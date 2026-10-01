# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Why did the boolean subtract not change the volume, and where should the port go?"""
import os
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
PROJ = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919\base_pifa.cst")


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


tool("cst_quit_tool")
tool("cst_connect_tool", launch_if_needed=True)
tool("cst_open_project_tool", path=str(PROJ))

s = S()
print("=" * 78)
print("HISTORY TREE (what actually happened)")
print("=" * 78)
try:
    s.run_vba('Sub Main\nDim i As Long, n As Long, t As String\n'
              'On Error Resume Next\nn = _GetHistory()\n'
              'For i = 1 To n\n'
              't = t & i & " | " & GetHistoryName(i) & vbLf\nNext i\n'
              'On Error GoTo 0\nReportInformationToWindow "H=" & t\nEnd Sub\n')
    for m in reversed(s.messages(limit=15)):
        if m["text"].startswith("H="):
            for line in m["text"][2:].splitlines():
                if line.strip():
                    print("   ", line.strip())
            break
except Exception as exc:  # noqa: BLE001
    print("  history read failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("SOLIDS - does slot_feed / slot_main still exist?")
print("=" * 78)
try:
    s.run_vba('Sub Main\nDim n As Long, i As Long, nm As String, t As String\n'
              'On Error Resume Next\nn = Solid.GetNumberOfShapes()\n'
              'For i = 0 To n - 1\n'
              'nm = Solid.GetNameOfShapeFromIndex(i)\n'
              't = t & nm & " | mat=" & Solid.GetMaterialNameForShape(nm)'
              ' & " | vol=" & Solid.GetVolume(nm) & vbLf\nNext i\n'
              'On Error GoTo 0\nReportInformationToWindow "S=" & t\nEnd Sub\n')
    for m in reversed(s.messages(limit=15)):
        if m["text"].startswith("S="):
            for line in m["text"][2:].splitlines():
                if line.strip():
                    print("   ", line.strip())
            break
except Exception as exc:  # noqa: BLE001
    print("  failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("PORT definition as stored")
print("=" * 78)
try:
    s.run_vba('Sub Main\nDim t As String\nOn Error Resume Next\n'
              't = "type=" & Port.GetType(1) & " | Z=" & Port.GetImpedance(1)\n'
              't = t & " | p1=" & Port.GetP1X(1) & "," & Port.GetP1Y(1) & "," & Port.GetP1Z(1)\n'
              't = t & " | p2=" & Port.GetP2X(1) & "," & Port.GetP2Y(1) & "," & Port.GetP2Z(1)\n'
              'On Error GoTo 0\nReportInformationToWindow "P=" & t\nEnd Sub\n')
    for m in reversed(s.messages(limit=15)):
        if m["text"].startswith("P="):
            print("   ", m["text"][2:])
            break
except Exception as exc:  # noqa: BLE001
    print("  failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("MESH / solver state (to confirm nothing forbidden was disturbed)")
print("=" * 78)
for label, code in (
    ("mesh", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
             't = "type=" & Mesh.MeshType\n'
             'On Error Resume Next\nt = t & " stepsTet=" & Mesh.StepsPerWavelengthTet\n'
             't = t & " minStepTet=" & Mesh.MinimumStepNumberTet\n'
             'On Error GoTo 0\nReportInformationToWindow "M=" & t\nEnd Sub\n'),
    ("boundary", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                 't = Boundary.Xmin & "," & Boundary.Xmax & "," & Boundary.Ymin & ","'
                 ' & Boundary.Ymax & "," & Boundary.Zmin & "," & Boundary.Zmax\n'
                 'On Error GoTo 0\nReportInformationToWindow "B=" & t\nEnd Sub\n'),
):
    try:
        s.run_vba(code)
        for m in reversed(s.messages(limit=12)):
            if m["text"][:2] in ("M=", "B="):
                print(f"   {label}: {m['text'][2:]}")
                break
    except Exception as exc:  # noqa: BLE001
        print(f"   {label}: failed {str(exc)[:90]}")

tool("cst_quit_tool")
