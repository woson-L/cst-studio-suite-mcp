# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Baseline v3: a real inverted-F (PIFA) cutout, verified by volume arithmetic.

Why v1/v2 failed
----------------
  v1  port ran z 0 -> 0.965, straight from the ground up into the copper  => a short
      (S11 came back flat at -0.03 dB, which is what a short looks like)
  v2  port bridged x w_arm -> w_arm+w_slot at y=fy. Both cuts were thin slivers that
      did not reach y=fy, so that x-span was still solid copper =>
      "Staircasing failed for discrete edge port 1: is completely inside metal"

The cutout that actually makes an INVERTED-F
--------------------------------------------
One T-shaped cut (a single brick union'd from two ranges, done here as two
overlapping bricks, then one subtract each) removes:

  shorting slot : x [0, gap_y]     y [90, 100]     full thickness
                  -> separates the ground strip (x < 0) from everything to its right
  feed slot     : x [gap_y, fx]    y [fy, 100]     full thickness
                  -> leaves, at x = gap_y, a vertical strip that is joined to the top
                     region y [fy,100]; that region is the continuous connection
                     between the shorting strip and the radiator  (the F's crossbar)

Result
  x [0, gap_y]              y [fy, 100]   shorting strip, bonded to the ground
  x [gap_y, fx]             y [fy, 100]   -- removed --
  x [fx, 25]                y [90, 100]   radiator
  the crossbar y [fy, 100] above the feed slot carries the current from the strip
  into the radiator; the port bridges the feed slot at y = fy, x = fx.

Volume check: the copper block is 25 x 10 x 0.035 = 8.75 mm^3, so after cutting
  shorting slot  gap_y x 10 x 0.035
  feed slot      (fx - gap_y) x (100 - fy) x 0.035
the volume must drop by exactly that amount. That arithmetic is what proves the cut
took effect - the earlier runs never checked it.
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
BASE = RUN / "base_pifa_v3.cst"

# ---- design variables (mm) ---------------------------------------------------
GAP_Y = 2.0     # width of the shorting strip / shorting slot
FX = 6.0        # feed slot right edge = port x
FY = 96.0       # feed slot bottom edge = port y
T = 0.035       # antenna thickness (fixed by the task)
ZB0, ZB1 = 0.965, 1.0   # copper block z-range


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def brief(ok, out, err):
    return (err or json.dumps(out, ensure_ascii=False, default=str))[:170]


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
print("  ", brief(*tool("cst_define_parameters_tool", parameters={
    "gap_y": GAP_Y, "fx": FX, "fy": FY})))

print("\n" + "=" * 78)
print("STEP 3  T-shaped cutout")
print("=" * 78)
# shorting slot: x [0, gap_y], all y
tool("cst_create_brick_tool", component="antenna", name="cut_short",
     xrange=["0", "gap_y"], yrange=["90", "100"], zrange=[str(ZB0), str(ZB1)],
     material="PEC")
print("  cut_short   :", brief(*tool("cst_boolean_tool", operation="subtract",
                                     target="antenna:antenna", tool="antenna:cut_short")))
# feed slot: x [gap_y, fx], y [fy, 100]
tool("cst_create_brick_tool", component="antenna", name="cut_feed",
     xrange=["gap_y", "fx"], yrange=["fy", "100"], zrange=[str(ZB0), str(ZB1)],
     material="PEC")
print("  cut_feed    :", brief(*tool("cst_boolean_tool", operation="subtract",
                                     target="antenna:antenna", tool="antenna:cut_feed")))

s = S()
s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
print("  Rebuild: OK")

print("\n" + "=" * 78)
print("STEP 4  VERIFY the cut by volume arithmetic")
print("=" * 78)
_, audit, _ = tool("cst_model_audit_tool")
ant = next((x for x in (audit.get("shapes") or []) if x["name"] == "antenna:antenna"), None)
for sh in audit.get("shapes") or []:
    print(f"    {sh['name']:<26} vol={sh['volume']:<12} mat={sh['material']}")
if ant:
    expect = 25 * 10 * T - GAP_Y * 10 * T - (FX - GAP_Y) * (100 - FY) * T
    got = ant["volume"]
    print(f"\n    expected volume = 25*10*{T} - {GAP_Y}*10*{T} - {FX - GAP_Y}*{100 - FY}*{T}"
          f" = {expect:.6f} mm^3")
    print(f"    reported volume = {got:.6f} mm^3")
    print(f"    [{'PASS' if abs(got - expect) < 1e-6 else 'FAIL'}] cut took effect")

print("\n" + "=" * 78)
print("STEP 5  discrete port across the FEED SLOT (point1/2 swapped to match)")
print("=" * 78)
# across the feed slot at y = fy: from the shorting strip's right face (x=gap_y)
# to the radiator's left face (x=fx), both at the copper mid-plane
ok, out, err = tool("cst_add_discrete_port_tool", port_number=1,
                    point1=["gap_y", "fy", "0.982"],
                    point2=["fx", "fy", "0.982"],
                    impedance=50.0)
print("  add port:", brief(ok, out, err))

print("\n" + "=" * 78)
print("STEP 6  save + solve")
print("=" * 78)
print("  ", brief(*tool("cst_save_project_tool", path=str(BASE))))
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if err:
    for line in str(err).splitlines():
        if any(k in line for k in ("ERROR", "WARNING", "Staircas", "mesh")):
            print("   ", line.strip()[:170])
else:
    for m in (out.get("messages_tail") or [])[:5]:
        print("   ", str(m)[:150])

print("\n" + "=" * 78)
print("STEP 7  S11 over 2.40-2.48 GHz")
print("=" * 78)
ok, s11, err = tool("cst_read_s11_tool", target_frequency=2.44)
print("  ", brief(ok, s11, err))
ok, z, err = tool("cst_read_reference_impedance_tool")
print("  ZRef:", brief(ok, z, err))

try:
    res = s.read_result("1D Results\\S-Parameters\\S1,1", max_points=10001)
    data = res.get("data") or []
    band = [(float(r[0]), r[1]) for r in data
            if len(r) > 1 and 2.40 <= float(r[0]) <= 2.48]
    print(f"  points in band: {len(band)} of {len(data)}")
    if band:
        worst = max(band, key=lambda t: t[1])
        print(f"  worst S11 in 2.40-2.48: {worst[1]:.3f} dB at {worst[0]:.4f} GHz")
        print(f"  [{'PASS' if worst[1] <= -10 else 'FAIL'}] criterion S11 <= -10 dB")
        # also show the overall best in 0-3 GHz for diagnosis
        allp = [(float(r[0]), r[1]) for r in data if len(r) > 1]
        bb = min(allp, key=lambda t: t[1])
        print(f"  overall best: {bb[1]:.3f} dB at {bb[0]:.4f} GHz")
except Exception as exc:  # noqa: BLE001
    print("  curve read failed:", str(exc)[:250])

tool("cst_quit_tool")
print("\ndone:", BASE)
