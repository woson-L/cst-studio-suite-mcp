# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919: shape Components/antenna/antenna into a PIFA and solve a baseline.

Physical reading of the source project
--------------------------------------
  component1:mainpcb   copper 100x100x1    z 0..1    = board + ground plane
  antenna:substrate    FR-4  25x10x0.965   z 0..0.965, x 0..25, y 90..100
  antenna:antenna      copper 25x10x0.035  z 0.965..1, same xy footprint
                       -> currently a SOLID copper block, i.e. no antenna shape yet

The copper block sits directly ON the FR-4, and the FR-4 sits directly on the board
copper. That is a PIFA: the block is the radiator, its left edge is the shorting wall
it shares with the ground, and the feed is a port through the FR-4 from the ground to
the radiator.

Shaping the PIFA
----------------
Two rectangular cuts in the copper block (both are plain boolean subtractions, no new
parameters change anything the user forbade):

  slot_feed : x [0, w_arm]           y [ys, 100]   z = whole thickness
              frees the radiator from the ground
  slot_main : x [w_arm, w_arm+w_slot] y [90, 100]   z = whole thickness
              cuts the slot between the shorting arm and the radiator

Resulting shape:
  x 0 .. w_arm          y ys .. 100     shorting arm, still bonded to the ground
  x w_arm+w_slot .. 25  y 90 .. 100     radiator
  joined at y = ys into an inverted-F / PIFA current path.

Feed: discrete port, 50 ohm, spanning z from the ground top (z = 0) up through the
FR-4 to the radiator underside (z = 0.965), placed inside the radiator footprint.
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

REG = mcp_server.registry
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
BASE = RUN / "base_pifa.cst"
SRC_WORK = RUN / "BT-20260919.cst"


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def show(label, ok, out, err):
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    print(f"        {(err or json.dumps(out, ensure_ascii=False, default=str))[:230]}")


print("=" * 78)
print("STEP 1  start from a fresh copy of the source (so this is repeatable)")
print("=" * 78)
tool("cst_quit_tool")
if BASE.exists():
    BASE.unlink()
if BASE.with_suffix("").is_dir():
    shutil.rmtree(BASE.with_suffix(""))
shutil.copy2(SRC_WORK, BASE)
shutil.copytree(SRC_WORK.with_suffix(""), BASE.with_suffix(""))
print(f"  cold copy -> {BASE.name}")

ok, conn, err = tool("cst_connect_tool", launch_if_needed=True)
print("  connect:", (conn or {}).get("design_environment_pid") or err)
ok, proj, err = tool("cst_open_project_tool", path=str(BASE))
print("  open:", (proj or {}).get("active_project", {}).get("filename") or err)

print("\n" + "=" * 78)
print("STEP 2  define the antenna parameters (design variables to optimise)")
print("=" * 78)
# Units are mm / GHz (read from the project earlier).
show("define parameters", *tool("cst_define_parameters_tool", parameters={
    "w_arm": 1.0,      # width of the shorting arm strip (x), mm
    "w_slot": 4.0,     # width of the slot between arm and radiator (x), mm
    "ys": 2.0,         # arm bottom edge (y); arm spans ys..100
    "fx": 8.25,        # port x position (must be >= w_arm+w_slot)
    "fy": 95.0,        # port y position
}))

print("\n" + "=" * 78)
print("STEP 3  cut the PIFA shape out of the solid copper block")
print("=" * 78)
# cut 1: remove the strip x [0, w_arm] above ys -> frees the radiator from ground
show("create slot_feed brick", *tool("cst_create_brick_tool",
     component="antenna", name="slot_feed",
     xrange=["0", "w_arm"], yrange=["ys", "100"],
     zrange=["0.965", "1.0"], material="PEC"))
show("subtract slot_feed", *tool("cst_boolean_tool",
     operation="subtract", target="antenna:antenna", tool="antenna:slot_feed"))

# cut 2: remove x [w_arm, w_arm+w_slot], all y -> separates arm from radiator
show("create slot_main brick", *tool("cst_create_brick_tool",
     component="antenna", name="slot_main",
     xrange=["w_arm", "w_arm+w_slot"], yrange=["90", "100"],
     zrange=["0.965", "1.0"], material="PEC"))
show("subtract slot_main", *tool("cst_boolean_tool",
     operation="subtract", target="antenna:antenna", tool="antenna:slot_main"))

print("\n" + "=" * 78)
print("STEP 4  verify the shape is now an inverted-F / PIFA")
print("=" * 78)
_, audit, _ = tool("cst_model_audit_tool")
for s in audit.get("shapes") or []:
    b = s["bbox"]
    dims = (round(b["x"][1] - b["x"][0], 4), round(b["y"][1] - b["y"][0], 4),
            round(b["z"][1] - b["z"][0], 4))
    print(f"    {s['name']:<26} {s['material']:<18} vol={s['volume']:<10} size={dims}")

print("\n" + "=" * 78)
print("STEP 5  feed: discrete port, 50 ohm, through the FR-4")
print("=" * 78)
# spans z 0 (ground top) .. 0.965 (radiator underside), inside the radiator footprint
show("add discrete port", *tool("cst_add_discrete_port_tool",
     port_number=1, point1=["fx", "fy", "0"], point2=["fx", "fy", "0.965"],
     impedance=50.0))
_, ports, _ = tool("cst_list_ports_tool")
print("    ports:", json.dumps(ports, ensure_ascii=False, default=str)[:200])

print("\n" + "=" * 78)
print("STEP 6  solver settings (UNCHANGED - source already correct)")
print("=" * 78)
_, freq, _ = tool("cst_frequency_overview_tool")
print("    band/solver:", json.dumps(freq, ensure_ascii=False, default=str)[:200])
print("    -> HF Time Domain, 0-3 GHz, no monitors, no symmetry. Left as-is.")

print("\n" + "=" * 78)
print("STEP 7  save and solve the baseline")
print("=" * 78)
show("save", *tool("cst_save_project_tool", path=str(BASE)))
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print(f"  [{'OK ' if ok else 'FAIL'}] solve")
if err:
    print("        ", err[:700])
else:
    for m in (out.get("messages_tail") or [])[:6]:
        print("        ", str(m)[:170])

print("\n" + "=" * 78)
print("STEP 8  read S11 and evaluate the 2.40-2.48 GHz criterion")
print("=" * 78)
ok, s11, err = tool("cst_read_s11_tool", target_frequency=2.44)
print("    read_s11:", json.dumps(s11, ensure_ascii=False, default=str)[:260] if ok else err)
ok, z, err = tool("cst_read_reference_impedance_tool")
print("    ZRef    :", json.dumps(z, ensure_ascii=False, default=str)[:160] if ok else err)
_, res, _ = tool("cst_list_results_tool")
print(f"    result tree items: {res.get('count')}")

print("\ndone. working project:", BASE)
