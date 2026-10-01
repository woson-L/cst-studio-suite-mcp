"""Definitive 123.cst task with a domain small enough to be solvable in the FD solver.

Why the boundary is explicit rather than `expanded open`:
  the band 0-100 MHz means a 3000 mm wavelength. `expanded open` adds about a
  quarter wavelength (750 mm) on every side, giving a ~1550 mm domain. Resolving the
  2 mm gap then needs ~50-300 steps across that domain (millions of elements), which
  is why the mesh never finished and the earlier attempts failed with
  "Could not compute preconditioner".
  A tight, explicitly sized box keeps the mesh small so the discrete-port task can
  actually be solved and its S-parameters read.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
os.environ["CST_DESIGN_ENVIRONMENT_EXE"] = (
    r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
)
os.environ["CST_MCP_WORKSPACE"] = r"C:\CST_MCP_workspace"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_server  # noqa: E402

REG = mcp_server.registry
PROJECT = r"C:\CST_MCP_workspace\source\123.cst"
LOG = Path(__file__).resolve().parents[1] / "tests" / "evidence" / "mcp_calls_123.jsonl"
LOG.parent.mkdir(parents=True, exist_ok=True)
LOG.write_text("", encoding="utf-8")

N = 0
FAILED = []


def call(tool, **args):
    global N
    N += 1
    spec = REG.get(tool)
    t0 = time.time()
    try:
        out = spec.handler(**args)
        ok = not (isinstance(out, dict) and out.get("ok") is False)
        err = None
    except Exception as exc:  # noqa: BLE001
        out, ok, err = None, False, f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - t0, 2)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"n": N, "tool": tool, "category": spec.category,
                             "args": args, "ok": ok, "elapsed_s": elapsed,
                             "result": out, "error": err},
                            ensure_ascii=False, default=str) + "\n")
    print(f"[{N:>2}] {'OK  ' if ok else 'FAIL'} {tool}"
          f"({json.dumps(args, ensure_ascii=False, default=str)[:120]})")
    print(f"       -> {(err or json.dumps(out, ensure_ascii=False, default=str))[:300]}")
    if not ok:
        FAILED.append((N, tool, (err or str(out))[:300]))
    return ok, out, err


print("=" * 78)
print("STEP 1  environment")
print("=" * 78)
call("cst_quit_tool")
call("cst_health_check_tool")
call("cst_connect_tool", launch_if_needed=True)

print("\n" + "=" * 78)
print("STEP 2  create 123.cst")
print("=" * 78)
ok, _, _ = call("cst_new_project_tool", project_type="mws", path=PROJECT)
if not ok:
    raise SystemExit("cannot create the project")

print("\n" + "=" * 78)
print("STEP 3  units (mm, MHz) and parameters")
print("=" * 78)
# Units.SetUnit is the documented, working form. It must be issued for Frequency so
# the 0-100 band below is MHz; otherwise it would be read as 0-100 GHz.
call("cst_run_vba_tool", vba_code=(
    "Sub Main\nWith Units\n .SetUnit (\"Length\", \"mm\")\n"
    " .SetUnit (\"Frequency\", \"MHz\")\nEnd With\nEnd Sub"))
call("cst_define_parameters_tool",
     parameters={"L": 50, "gap": 2, "tsheet": 5})

print("\n" + "=" * 78)
print("STEP 4  50 mm cube, material iron")
print("=" * 78)
call("cst_load_material_from_library_tool", library_path="Iron")
call("cst_create_brick_tool", component="parts", name="box",
     xrange=["-L/2", "L/2"], yrange=["-L/2", "L/2"], zrange=["0", "L"],
     material="Iron")
call("cst_model_audit_tool")

print("\n" + "=" * 78)
print("STEP 5  50 x 50 x 5 mm sheet, 2 mm below the box, material PEC")
print("=" * 78)
call("cst_create_brick_tool", component="parts", name="sheet",
     xrange=["-L/2", "L/2"], yrange=["-L/2", "L/2"],
     zrange=["-gap-tsheet", "-gap"], material="PEC")
call("cst_model_audit_tool")

print("\n" + "=" * 78)
print("STEP 6  discrete port at the sheet centre, connecting sheet top to box bottom")
print("=" * 78)
call("cst_add_discrete_port_tool", port_number=1,
     point1=[0, 0, "-gap"], point2=[0, 0, "0"], impedance=50.0)
call("cst_list_ports_tool")

print("\n" + "=" * 78)
print("STEP 7  frequency domain solver, 0 - 100 MHz")
print("=" * 78)
call("cst_set_solver_tool", solver="HF Frequency Domain")
call("cst_get_solver_tool")
call("cst_set_frequency_range_tool", fmin=0, fmax=100, unit="MHz")
call("cst_frequency_overview_tool")
call("cst_configure_fd_solver_tool", mesh="Tetrahedral", sweep="General Purpose",
     order="Second", accuracy="1e-4")
call("cst_set_background_tool", epsilon=1.0, mue=1.0, apply_in_all_directions=True)
# A tight domain instead of "expanded open": see the module docstring.
call("cst_set_boundary_tool", xmin="open", xmax="open", ymin="open", ymax="open",
     zmin="open", zmax="open")
call("cst_set_mesh_tool", mesh_type="Tetrahedral", steps_per_wavelength=8)

print("\n" + "=" * 78)
print("STEP 8  solve")
print("=" * 78)
call("cst_save_project_tool", path=PROJECT, overwrite=True)
call("cst_run_solver_tool")
call("cst_messages_tool", limit=20)

print("\n" + "=" * 78)
print("STEP 9  S-parameters and verification")
print("=" * 78)
call("cst_list_results_tool")
call("cst_read_s11_tool", target_frequency=100)
call("cst_read_reference_impedance_tool")
call("cst_energy_summary_tool", frequency=100)
call("cst_export_touchstone_tool",
     filename=r"C:\CST_MCP_workspace\evidence\123_s11", impedance=50.0, data_format="RI")
call("cst_export_ascii_tool", tree_path="1D Results\\S-Parameters\\S1,1",
     filename=r"C:\CST_MCP_workspace\evidence\123_s11.txt")

print("\n" + "=" * 78)
print(f"TOTAL tool calls: {N}   failed: {len(FAILED)}")
for row in FAILED:
    print("   ", row)
print("=" * 78)
