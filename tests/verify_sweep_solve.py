"""Sweep WITH solving, reusing the geometry+port that already solved in this session.

Proven-good base (from the earlier 123.cst verification):
  PEC sheet, a gap of `gap` mm above it, discrete port across the gap on the centre
  axis, HF Time Domain, 0-100 MHz. That configuration solved.

Only change: the swept parameter is `gap`, and both plates are built-in PEC so the
rebuild does not depend on a library material.
"""
import json
import os
import shutil
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
PROJECT = BASE / "gap_sweep.cst"


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
print("STEP 1  base model: two PEC plates, gap = variable, discrete port across it")
print("=" * 76)
kill()
for p in (PROJECT, BASE / "gap_sweep"):
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.is_file():
        p.unlink()

s = S()
s.connect(launch_if_needed=True)
s.new_project(project_type="mws", path=str(PROJECT))
s.run_vba('Sub Main\nWith Units\n .SetUnit ("Length", "mm")\n'
          ' .SetUnit ("Frequency", "MHz")\nEnd With\nEnd Sub\n')
s.set_parameters({"L": 50, "gap": 2, "tsheet": 5})
s.add_history("top", 'With Brick\n .Reset\n .Name "top"\n .Component "parts"\n'
                     ' .Material "PEC"\n .Xrange "-L/2", "L/2"\n .Yrange "-L/2", "L/2"\n'
                     ' .Zrange "0", "L"\n .Create\nEnd With')
s.add_history("bottom", 'With Brick\n .Reset\n .Name "bottom"\n .Component "parts"\n'
                        ' .Material "PEC"\n .Xrange "-L/2", "L/2"\n .Yrange "-L/2", "L/2"\n'
                        ' .Zrange "-gap-tsheet", "-gap"\n .Create\nEnd With')
s.add_history("port", 'With DiscretePort\n .Reset\n .PortNumber "1"\n .Type "SParameter"\n'
                      ' .SetP1 "False", "0", "0", "-gap"\n'
                      ' .SetP2 "False", "0", "0", "0"\n'
                      ' .Impedance "50"\n .Create\nEnd With')
tool("cst_set_solver_tool", solver="HF Time Domain")
tool("cst_set_frequency_range_tool", fmin=0, fmax=100, unit="MHz")
tool("cst_configure_td_solver_tool", accuracy="-30", mesh_type="Hexahedral")
tool("cst_set_boundary_tool", all="open")
tool("cst_set_background_tool", epsilon=1.0, mue=1.0, apply_in_all_directions=True)
tool("cst_set_mesh_tool", mesh_type="HexahedralFIT", lines_per_wavelength=20)
s.save_project(str(PROJECT))
print("  built:", PROJECT.name, s.list_parameters())

print("\n  single solve first (prove the base model)...")
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  ok =", ok)
if err:
    print("  error:", err[:450])
elif out:
    for m in (out.get("messages_tail") or [])[:4]:
        print("   ", str(m)[:140])
s.close_project()
kill()

if not ok:
    print("\n  base model still not solving; stopping so the sweep is not blamed")
    tool("cst_quit_tool")
    raise SystemExit(1)

print("\n" + "=" * 76)
print("STEP 2  sweep gap = 2:5:1  WITH solving, S-parameters per case")
print("=" * 76)
ok, out, err = tool("cst_sweep_run_tool",
                    project_path=str(PROJECT), parameters={"gap": "2:5:1"},
                    mode="single", run_solver=True, export_touchstone=True,
                    result_tree_paths=["1D Results\\S-Parameters\\S1,1"],
                    close_after_case=True)
print("  ok =", ok)
if err:
    print("  error:", err[:500])
else:
    print("  case_count :", out.get("case_count"))
    print("  completed  :", out.get("completed"), " failed:", out.get("failed"))
    for row in (out.get("cases") or []):
        print("  ", json.dumps(row, ensure_ascii=False, default=str)[:250])

if out:
    base = Path(out["output_dir"])
    print("\n  per-case S-parameter files:")
    for f in sorted(base.rglob("*.s*p")):
        print(f"    {f.relative_to(base)}  ({f.stat().st_size} B)")
    csv = Path(out["summary_csv"])
    if csv.is_file():
        print("\n  sweep_summary.csv:")
        for line in csv.read_text(encoding="utf-8").splitlines():
            print("   ", line[:170])

tool("cst_quit_tool")
kill()
print("\ndone")
