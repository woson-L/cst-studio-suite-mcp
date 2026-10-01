# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Baseline v2: force a rebuild after cutting, then feed across the slot gap.

Two fixes over v1:
  * explicit Rebuild after the boolean cuts (v1 cut then audited without a rebuild,
    so the reported volume was the pre-cut value);
  * the port is placed ACROSS the slot gap (in y), not across the FR-4 thickness.
    v1's port ran z=0 -> 0.965 straight from the ground into the copper, which is a
    short: S11 came back flat at -0.03 dB, exactly what a short looks like.
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
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
SRC = RUN / "BT-20260919.cst"
BASE = RUN / "base_pifa_v2.cst"


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def brief(ok, out, err):
    return (err or json.dumps(out, ensure_ascii=False, default=str))[:180]


print("=" * 78)
print("STEP 1  cold copy + open")
print("=" * 78)
tool("cst_quit_tool")
for p in (BASE, BASE.with_suffix("")):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.is_file():
        p.unlink()
shutil.copy2(SRC, BASE)
shutil.copytree(SRC.with_suffix(""), BASE.with_suffix(""))
tool("cst_connect_tool", launch_if_needed=True)
ok, out, err = tool("cst_open_project_tool", path=str(BASE))
print("  opened:", (out or {}).get("active_project", {}).get("filename") or err)

print("\n" + "=" * 78)
print("STEP 2  parameters")
print("=" * 78)
# PIFA geometry:
#   arm      x [0, w_arm]            y [ys, 100]   copper bonded to ground (short)
#   slot     x [w_arm, w_arm+w_slot] y [90, 100]
#   radiator x [w_arm+w_slot, 25]    y [90, 100]
# feed sits ACROSS the slot (y direction) at z = 0.965 (copper plane of the block)
ok, out, err = tool("cst_define_parameters_tool", parameters={
    "w_arm": 1.5, "w_slot": 3.0, "ys": 3.0, "fy": 96.0,
})
print("  ", brief(ok, out, err))

print("\n" + "=" * 78)
print("STEP 3  cut the two slots, then REBUILD")
print("=" * 78)
tool("cst_create_brick_tool", component="antenna", name="slot_feed",
     xrange=["0", "w_arm"], yrange=["ys", "100"],
     zrange=["0.965", "1.0"], material="PEC")
ok, out, err = tool("cst_boolean_tool", operation="subtract",
                    target="antenna:antenna", tool="antenna:slot_feed")
print("  subtract slot_feed:", brief(ok, out, err))

tool("cst_create_brick_tool", component="antenna", name="slot_main",
     xrange=["w_arm", "w_arm+w_slot"], yrange=["90", "100"],
     zrange=["0.965", "1.0"], material="PEC")
ok, out, err = tool("cst_boolean_tool", operation="subtract",
                    target="antenna:antenna", tool="antenna:slot_main")
print("  subtract slot_main:", brief(ok, out, err))

s = S()
try:
    s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
    print("  explicit Rebuild: OK")
except Exception as exc:  # noqa: BLE001
    print("  explicit Rebuild FAILED:", str(exc)[:200])

_, audit, _ = tool("cst_model_audit_tool")
print("\n  after rebuild:")
for sh in audit.get("shapes") or []:
    b = sh["bbox"]
    print(f"    {sh['name']:<26} vol={sh['volume']:<12} "
          f"x={b['x']} y={b['y']} z={b['z']}")

print("\n" + "=" * 78)
print("STEP 4  feed ACROSS the slot (y direction) at z = 0.965")
print("=" * 78)
# from the shorting arm's right face to the radiator's left face, same y, same z
ok, out, err = tool("cst_add_discrete_port_tool", port_number=1,
                    point1=["w_arm", "fy", "0.965"],
                    point2=["w_arm+w_slot", "fy", "0.965"],
                    impedance=50.0)
print("  add port:", brief(ok, out, err))

print("\n" + "=" * 78)
print("STEP 5  save and solve")
print("=" * 78)
tool("cst_save_project_tool", path=str(BASE))
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if err:
    print("   ", err[:600])
else:
    for m in (out.get("messages_tail") or [])[:5]:
        print("   ", str(m)[:150])

print("\n" + "=" * 78)
print("STEP 6  S11 across 0-3 GHz, criterion check at 2.40-2.48")
print("=" * 78)
ok, s11, err = tool("cst_read_s11_tool", target_frequency=2.44)
print("  read_s11:", brief(ok, s11, err))
ok, z, err = tool("cst_read_reference_impedance_tool")
print("  ZRef:", brief(ok, z, err))

# pull the whole curve and evaluate the band properly
try:
    res = s.read_result("1D Results\\S-Parameters\\S1,1", max_points=10001)
    data = res.get("data") or []
    band = []
    for row in data:
        try:
            f = float(row[0])
        except (TypeError, ValueError, IndexError):
            continue
        if 2.40 <= f <= 2.48:
            band.append((f, row[1]))
    print(f"  curve points: {len(data)}   points inside 2.40-2.48 GHz: {len(band)}")
    if band:
        import math
        worst = None
        for f, v in band:
            db = v if isinstance(v, (int, float)) else None
            if db is None:
                continue
            if worst is None or db > worst[1]:
                worst = (f, db)
        print(f"  worst S11 in band: {worst[1]:.3f} dB at {worst[0]:.4f} GHz")
        print(f"  CRITERION (S11 <= -10 dB over 2.40-2.48): "
              f"{'PASS' if worst[1] <= -10 else 'FAIL'}")
except Exception as exc:  # noqa: BLE001
    print("  curve read failed:", str(exc)[:300])

tool("cst_quit_tool")
print("\ndone:", BASE)
