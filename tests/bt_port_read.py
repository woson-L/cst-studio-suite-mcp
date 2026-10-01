# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Read the port geometry and the parts of the history the first pass missed.

Read-only: opens a throwaway copy, prints, saves nothing.
"""
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
DESK = Path(r"C:\CST_MCP_workspace\source")
SRC = DESK / "BT-20260919.cst"
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
COPY = RUN / "readonly_probe.cst"

REG.get("cst_quit_tool").handler()
for p in (COPY, COPY.with_suffix("")):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.is_file():
        p.unlink()
shutil.copy2(SRC, COPY)
if SRC.with_suffix("").is_dir():
    shutil.copytree(SRC.with_suffix(""), COPY.with_suffix(""))
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(COPY))
s = S()

print("=" * 78)
print("A. PORT 1 - exact geometry")
print("=" * 78)
try:
    hist = s.model3d()._GetHistory()
    entries = hist["list"] if isinstance(hist, dict) else hist
    for e in entries:
        if isinstance(e, dict) and "discrete port" in str(e.get("name", "")).lower():
            print("   history entry:")
            for line in str(e.get("contents", "")).splitlines():
                print("     ", line)
except Exception as exc:  # noqa: BLE001
    print("   history read failed:", str(exc)[:200])

print("\n   raw port properties:")
for label, code in (
    ("type/impedance", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                       't = "type=" & Port.GetType(1) & " Z=" & Port.GetNumber(1)\n'
                       'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
):
    try:
        s.run_vba(code)
        for m in reversed(s.messages(limit=10)):
            if m["text"].startswith("R="):
                print(f"     {label}: {m['text'][2:]}")
                break
    except Exception as exc:  # noqa: BLE001
        print(f"     {label}: {str(exc).splitlines()[-1][:100]}")

# the DiscretePort object reports its own endpoints via the history; read them back
s.run_vba('Sub Main\nDim t As String\nOn Error Resume Next\n'
          't = "P1=" & Port.GetP1X(1) & "," & Port.GetP1Y(1) & "," & Port.GetP1Z(1)\n'
          'On Error GoTo 0\nReportInformationToWindow "R2=" & t\nEnd Sub\n')
for m in reversed(s.messages(limit=10)):
    if m["text"].startswith("R2="):
        print("     ", m["text"][3:])
        break

print("\n" + "=" * 78)
print("B. ALL history entries (names only, to see the full build)")
print("=" * 78)
try:
    entries = hist["list"] if isinstance(hist, dict) else hist
    for i, e in enumerate(entries, 1):
        if isinstance(e, dict):
            flag = " !ERR" if e.get("error") else ""
            print(f"   {i:>3}. {e.get('name','?')}{flag}")
except Exception as exc:  # noqa: BLE001
    print("   failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("C. mesh / boundary / solver state (must not be changed)")
print("=" * 78)
for label, code in (
    ("solver_type", 'Sub Main\nReportInformationToWindow "R=" & GetSolverType()\nEnd Sub\n'),
    ("band", 'Sub Main\nOn Error Resume Next\n'
             'ReportInformationToWindow "R=" & Solver.GetFmin() & " - " & Solver.GetFmax()\n'
             'On Error GoTo 0\nEnd Sub\n'),
    ("mesh", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
             't = Mesh.MeshType\n'
             't = t & " | stepsTet=" & Mesh.StepsPerWavelengthTet\n'
             't = t & " | minStepTet=" & Mesh.MinimumStepNumberTet\n'
             'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
    ("boundary", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                 't = Boundary.Xmin & "|" & Boundary.Xmax & "|" & Boundary.Ymin & "|" & Boundary.Ymax'
                 ' & "|" & Boundary.Zmin & "|" & Boundary.Zmax\n'
                 'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
):
    try:
        s.run_vba(code)
        for m in reversed(s.messages(limit=10)):
            if m["text"].startswith("R="):
                print(f"   {label:<12} {m['text'][2:]}")
                break
    except Exception as exc:  # noqa: BLE001
        print(f"   {label:<12} <fail {str(exc).splitlines()[-1][:70]}>")

REG.get("cst_quit_tool").handler()
print("\ndone (nothing saved)")
