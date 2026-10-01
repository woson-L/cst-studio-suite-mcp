# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919: copy the source project to a run directory and inspect it read-only.

Skill rule: never modify the source project. Work on a copy, with its companion
folder. Nothing here writes to the model.
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime
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
SRC = Path(r"C:\CST_MCP_workspace\source\BT-20260919.cst")
STAMP = datetime.now().strftime("%Y%m%d")
RUN = Path(r"C:\CST_MCP_workspace") / "cst_runs" / f"bt_antenna_{STAMP}"
RUN.mkdir(parents=True, exist_ok=True)


def tool(name, **args):
    try:
        out = REG.get(name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


print("=" * 78)
print("STEP 1  copy source project (never touch the original)")
print("=" * 78)
work = RUN / SRC.name
if work.exists():
    work.unlink()
shutil.copy2(SRC, work)
src_dir = SRC.with_suffix("")
if src_dir.is_dir():
    dst_dir = work.with_suffix("")
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    print(f"  copied companion folder: {dst_dir.name}")
print(f"  source : {SRC}  ({SRC.stat().st_size} B)")
print(f"  working: {work}  ({work.stat().st_size} B)")
print(f"  run dir: {RUN}")

print("\n" + "=" * 78)
print("STEP 2  connect and open the COPY")
print("=" * 78)
tool("cst_quit_tool")
ok, conn, err = tool("cst_connect_tool", launch_if_needed=True)
print("  connect:", ok, (conn or {}).get("design_environment_pid") or err)
ok, proj, err = tool("cst_open_project_tool", path=str(work))
print("  open   :", ok, json.dumps(proj, ensure_ascii=False, default=str)[:200] if ok else err)

print("\n" + "=" * 78)
print("STEP 3  read-only inventory")
print("=" * 78)
_, info, _ = tool("cst_project_info_tool")
print("  active project:", json.dumps(info.get("active_project"), ensure_ascii=False, default=str))

_, params, _ = tool("cst_get_parameters_tool")
print(f"\n  PARAMETERS ({params.get('count')}):")
for k, v in (params.get("parameters") or {}).items():
    print(f"    {k:<16} = {v}")

_, audit, _ = tool("cst_model_audit_tool")
print(f"\n  SOLIDS ({audit.get('shape_count')}):")
for s in audit.get("shapes") or []:
    b = s["bbox"]
    dims = (round(b["x"][1] - b["x"][0], 4), round(b["y"][1] - b["y"][0], 4),
            round(b["z"][1] - b["z"][0], 4))
    print(f"    {s['name']:<28} mat={s['material']:<18} vol={s['volume']:<10} "
          f"size={dims}")
    print(f"        bbox x={b['x']} y={b['y']} z={b['z']}")

_, ports, _ = tool("cst_list_ports_tool")
print(f"\n  PORTS: {json.dumps(ports, ensure_ascii=False, default=str)[:400]}")

_, freq, _ = tool("cst_frequency_overview_tool")
print(f"\n  SOLVER/BAND: {json.dumps(freq, ensure_ascii=False, default=str)}")

_, sol, _ = tool("cst_get_solver_tool")
print(f"  solver tool: {json.dumps(sol, ensure_ascii=False, default=str)}")

_, results, _ = tool("cst_list_results_tool")
print(f"\n  RESULT TREE ({results.get('count')}):")
for item in (results.get("items") or [])[:25]:
    print(f"    {item}")

_, msgs, _ = tool("cst_messages_tool", limit=15)
print("\n  RECENT MESSAGES:")
for m in (msgs.get("messages") or [])[-12:]:
    print(f"    {m['type']}: {str(m['text'])[:150]}")

# raw reads that no tool exposes
print("\n" + "=" * 78)
print("STEP 4  settings the user forbids changing (record as fingerprints)")
print("=" * 78)
s = S()
for label, code in (
    ("units", 'Sub Main\nDim a As String, b As String, c As String\n'
              'On Error Resume Next\n'
              'a = Units.GetUnit ("Length")\nb = Units.GetUnit ("Frequency")\n'
              'c = Units.GetUnit ("Time")\nOn Error GoTo 0\n'
              'ReportInformationToWindow "R=" & a & "|" & b & "|" & c\nEnd Sub\n'),
    ("boundaries", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                   't = Boundary.Xmin & "|" & Boundary.Xmax & "|" & Boundary.Ymin & "|"'
                   ' & Boundary.Ymax & "|" & Boundary.Zmin & "|" & Boundary.Zmax\n'
                   'On Error GoTo 0\n'
                   'ReportInformationToWindow "R=" & t\nEnd Sub\n'),
    ("symmetry", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                 't = Boundary.Xsymmetry & "|" & Boundary.Ysymmetry & "|" & Boundary.Zsymmetry\n'
                 'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
    ("mesh", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
             't = Mesh.MeshType & "|stepsTet=" & Mesh.StepsPerWavelengthTet\n'
             't = t & "|minStepTet=" & Mesh.MinimumStepNumberTet\n'
             't = t & "|lines=" & Mesh.LinesPerWavelength\n'
             'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
    ("solver_cfg", 'Sub Main\nDim t As String\nOn Error Resume Next\n'
                   't = "method=" & FDSolver.GetMethodMesh() & "/" & FDSolver.GetMethodSweep()\n'
                   'On Error Resume Next\n'
                   't = t & "|accTet=" & FDSolver.GetAccuracyTet()\n'
                   't = t & "|orderTet=" & FDSolver.GetOrderTet()\n'
                   't = t & "|meshAdapt=" & FDSolver.GetMeshAdaptionTet()\n'
                   'On Error GoTo 0\nReportInformationToWindow "R=" & t\nEnd Sub\n'),
    ("monitors", 'Sub Main\nDim n As Long, i As Long, s As String\n'
                 'On Error Resume Next\nn = Monitor.GetNumberOfMonitors()\n'
                 's = "n=" & n\n'
                 'For i = 0 To n - 1\ns = s & "|" & Monitor.GetMonitorNameFromIndex(i)'
                 ' & ":" & Monitor.GetFieldTypeFromIndex(i) & "@" & Monitor.GetFrequencyFromIndex(i)\nNext i\n'
                 'On Error GoTo 0\nReportInformationToWindow "R=" & s\nEnd Sub\n'),
):
    try:
        s.run_vba(code)
        val = "?"
        for m in reversed(s.messages(limit=15)):
            if m["text"].startswith("R="):
                val = m["text"][2:]
                break
        print(f"  {label:<12} {val}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {label:<12} <read failed: {str(exc).splitlines()[-1][:90]}>")

# component / solid tree as CST actually stores it
try:
    s.run_vba('Sub Main\nDim s As String, i As Long, n As Long, nm As String\n'
              'On Error Resume Next\nn = Solid.GetNumberOfShapes()\n'
              's = ""\nFor i = 0 To n - 1\n'
              'nm = Solid.GetNameOfShapeFromIndex(i)\n'
              's = s & nm & " | " & Solid.GetMaterialNameForShape(nm) & vbLf\nNext i\n'
              'On Error GoTo 0\n'
              'ReportInformationToWindow "TREE=" & s\nEnd Sub\n')
    for m in reversed(s.messages(limit=15)):
        if m["text"].startswith("TREE="):
            print("\n  SOLID TREE (component:name):")
            for line in m["text"][5:].splitlines():
                if line.strip():
                    print(f"    {line.strip()}")
            break
except Exception as exc:  # noqa: BLE001
    print("  tree read failed:", str(exc)[:150])

print(f"\n  working copy left OPEN and UNSAVED for the next step: {work}")
Path(RUN / "run_dir.txt").write_text(str(RUN), encoding="utf-8")
print(f"  run dir: {RUN}")
