"""Verify the sweep tool on the user's exact example.

  box, material PEC, edge length = variable L, sweep L from 6 to 10 mm step 2 mm

Checks that the geometry ACTUALLY changes per case (bounding box + volume), not just
that the parameter value was written - the distinction that made the earlier
library-material run misleading.
"""
import json
import os
import subprocess
import sys
import time
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
BASE = Path(r"C:\CST_MCP_workspace\sweep_demo")
BASE.mkdir(parents=True, exist_ok=True)
PROJECT = BASE / "cube_L.cst"


def kill():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process -Name 'CST DESIGN ENVIRONMENT_AMD64','modeler_AMD64' "
                    "-ErrorAction SilentlyContinue | Stop-Process -Force"], capture_output=True)
    time.sleep(3)


def tool(name, **args):
    try:
        out = REG.get(name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


print("=" * 76)
print("STEP 1  build the base project: PEC cube with edge = L")
print("=" * 76)
kill()
for p in (PROJECT, BASE / "cube_L"):
    if p.is_dir():
        import shutil
        shutil.rmtree(p, ignore_errors=True)
    elif p.is_file():
        p.unlink()

s = S()
s.connect(launch_if_needed=True)
s.new_project(project_type="mws", path=str(PROJECT))
s.run_vba('Sub Main\nWith Units\n .SetUnit ("Length", "mm")\n'
          ' .SetUnit ("Frequency", "GHz")\nEnd With\nEnd Sub\n')
s.set_parameters({"L": 8})
s.add_history("cube", 'With Brick\n .Reset\n .Name "box"\n .Component "parts"\n'
                     ' .Material "PEC"\n'
                     ' .Xrange "-L/2", "L/2"\n .Yrange "-L/2", "L/2"\n'
                     ' .Zrange "-L/2", "L/2"\n .Create\nEnd With')
s.add_history("port", 'With DiscretePort\n .Reset\n .PortNumber "1"\n'
                      ' .Type "SParameter"\n'
                      ' .SetP1 "False", "-L/2", "0", "0"\n'
                      ' .SetP2 "False", "-L/2", "0", "L"\n'
                      ' .Impedance "50"\n .Create\nEnd With')
# solver/boundary/background are tool-level, not session methods
tool("cst_set_solver_tool", solver="HF Frequency Domain")
tool("cst_set_frequency_range_tool", fmin=2.0, fmax=4.0, unit="GHz")
tool("cst_set_boundary_tool", all="open")
tool("cst_set_background_tool", epsilon=1.0, mue=1.0)
s.save_project(str(PROJECT))
print("  built:", PROJECT.name, " L =", s.list_parameters().get("L"))
s.close_project()
kill()

print("\n" + "=" * 76)
print("STEP 2  preview the sweep  L = 6 : 10 : 2")
print("=" * 76)
ok, out, err = tool("cst_sweep_preview_tool", parameters={"L": "6:10:2"}, mode="single")
print("  ok =", ok)
if ok:
    print("  case_count =", out["case_count"])
    for c in out["cases"]:
        print("   ", c)
else:
    print("  error:", err)

print("\n" + "=" * 76)
print("STEP 3  run the sweep (solve OFF - parameter/geometry change only)")
print("=" * 76)
ok, out, err = tool("cst_sweep_run_tool", project_path=str(PROJECT),
                    parameters={"L": "6:10:2"}, mode="single",
                    run_solver=False, close_after_case=True)
print("  ok =", ok)
if err:
    print("  error:", err[:600])
else:
    print("  case_count :", out.get("case_count"))
    print("  output_dir :", out.get("output_dir"))
    print("  summary_csv:", out.get("summary_csv"))
    for row in (out.get("cases") or []):
        print("   ", json.dumps(row, ensure_ascii=False)[:220])

print("\n" + "=" * 76)
print("STEP 4  per-case geometry check: does the box ACTUALLY change size?")
print("=" * 76)
cases_dir = Path(out["output_dir"]) / "cases" if ok and out else None
if cases_dir and cases_dir.is_dir():
    for case in sorted(cases_dir.iterdir()):
        proj = case / f"{PROJECT.stem}.cst"
        if not proj.is_file():
            print(f"  {case.name}: no project file")
            continue
        kill()
        s2 = S()
        s2.connect(launch_if_needed=True)
        s2.open_project(str(proj))
        L = s2.list_parameters().get("L")
        s2.run_vba('Sub Main\n'
                   'Dim x1 As Double, x2 As Double, y1 As Double, y2 As Double, '
                   'z1 As Double, z2 As Double\n'
                   'Dim ok2 As Boolean\n'
                   'ok2 = Solid.GetLooseBoundingBoxOfShape("parts:box", x1, x2, y1, y2, z1, z2)\n'
                   'ReportInformationToWindow "BB=" & (x2-x1) & "," & (y2-y1) & "," & (z2-z1)\n'
                   'End Sub\n')
        bb = "?"
        for m in reversed(s2.messages(limit=15)):
            if "BB=" in m["text"]:
                bb = m["text"].split("BB=", 1)[1]
                break
        print(f"  {case.name}: L={L}  bbox size = {bb}")
        s2.close_project()
    kill()
else:
    print("  (no cases directory - sweep did not complete)")

ok2, q, _ = tool("cst_quit_tool")
print("\ndone")
