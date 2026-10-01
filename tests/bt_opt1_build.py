# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919-OPT1: reshape Components/antenna/antenna into an L (IFA-style)
monopole and solve.

Measured model (probe3.json):
    component1:mainpcb   Copper  x[0,100] y[0,100] z[0,1]      (ground, 25x10 window)
    antenna:antenna      Copper  x[0,25]  y[90.5,100] z[0,0.035]   <- the only editable solid
    antenna:substrate    FR-4    x[0,25]  y[90,100]  z[0.035,0.965]
    discrete port 1 at the middle of the y=90.5 edge of the plate (x = 12.5)

Only copper is removed; nothing is moved, no boundary/solver/mesh/monitor change.
Parameters AW/AH/AL are stored so the same script can be re-run at other sizes.
"""
import json
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

# ---------------------------------------------------------------- shape knobs
AW = float(os.environ.get("BT_AW", "3"))     # arm width  (x, mm)
AH = float(os.environ.get("BT_AH", "3"))     # arm height (y, mm)
AL = float(os.environ.get("BT_AL", "9.5"))   # horizontal arm length (mm)

REG = mcp_server.registry
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
PROJ = RUN / "BT-20260919-OPT1.cst"
TAG = os.environ.get("BT_TAG", f"L_AW{AW}_AH{AH}_AL{AL}")
CURVE = RUN / f"s11_{TAG}.json"


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def brief(ok, out, err, n=200):
    return (err or json.dumps(out, ensure_ascii=False, default=str))[:n]


print("=" * 78)
print(f"SHAPE  AW={AW} AH={AH} AL={AL}   tag={TAG}")
print("=" * 78)

REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(PROJ))
s = S()

print("\n--- port provenance (history 49-51) ---")
try:
    h = s.model3d()._GetHistory()
    entries = h.get("list") if isinstance(h, dict) else None
    if entries:
        for i in (48, 49, 50):
            if i < len(entries):
                e = entries[i]
                print(f"  [{i + 1}] {e.get('name')}: "
                      f"{str(e.get('contents'))[:400]}")
except Exception as exc:  # noqa: BLE001
    print("  history contents unavailable:", str(exc)[:200])

print("\n--- 1. parameters ---")
ok, out, err = tool("cst_define_parameters_tool",
                    parameters={"AW": AW, "AH": AH, "AL": AL})
print("  ", brief(ok, out, err))
ok, out, err = tool("cst_get_parameters_tool")
print("  readback:", brief(ok, out, err, 300))

print("\n--- 2. cut bricks (expressions, so a sweep can re-drive them) ---")
cuts = [
    ("cut_a", ["-1", "12.5-AW/2"], ["89", "101"], ["-0.05", "0.1"]),
    ("cut_b", ["12.5+AW/2", "26"], ["89", "100-AH"], ["-0.05", "0.1"]),
    ("cut_c", ["12.5-AW/2+AL", "26"], ["100-AH", "101"], ["-0.05", "0.1"]),
]
for name, xr, yr, zr in cuts:
    ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                        xrange=xr, yrange=yr, zrange=zr, material="PEC")
    print(f"  {name}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 160)}")

print("\n--- 3. subtract the cuts from antenna:antenna ---")
for name, *_ in cuts:
    ok, out, err = tool("cst_boolean_tool", operation="subtract",
                        target="antenna:antenna", tool=f"antenna:{name}")
    print(f"  subtract {name}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 160)}")

s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
ok, audit, err = tool("cst_model_audit_tool")
expect = 0.035 * (AW * 9.5 + AL * AH)
for sh in (audit or {}).get("shapes") or []:
    print(f"  {sh.get('name'):<24} vol={sh.get('volume')}  {sh.get('bbox')}")
print(f"  expected antenna volume = {expect:.4f} mm^3")

print("\n--- 4. save ---")
print("  ", brief(*tool("cst_save_project_tool", path=str(PROJ))))

print("\n--- 5. solve ---")
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if not ok:
    print("  ", str(err)[:900])

if ok:
    print("\n--- 6. S11 ---")
    try:
        res = s.read_result("1D Results\\S-Parameters\\S1,1", max_points=20001)
        data = [(float(r[0]), float(r[1])) for r in (res.get("data") or [])
                if len(r) > 1]
    except Exception as exc:  # noqa: BLE001
        data = []
        print("  read failed:", str(exc)[:300])
    if data:
        CURVE.write_text(json.dumps(data), encoding="utf-8")
        print(f"  points: {len(data)}  ({data[0][0]:.4f} .. {data[-1][0]:.4f} GHz)")
        band = [(f, v) for f, v in data if 2.40 <= f <= 2.48]
        if band:
            w = max(band, key=lambda t: t[1])
            print(f"  worst 2.40-2.48: {w[1]:.2f} dB @ {w[0]:.4f} GHz -> "
                  f"{'PASS' if w[1] <= -10 else 'FAIL'}")
        bb = min(data, key=lambda t: t[1])
        print(f"  best overall   : {bb[1]:.2f} dB @ {bb[0]:.4f} GHz")
        # -10 dB band edges around the global minimum
        lo = hi = None
        for f, v in data:
            if v <= -10:
                if lo is None:
                    lo = f
                hi = f
        print(f"  S11<=-10dB span: {lo} .. {hi} GHz")
        for f in (2.30, 2.40, 2.44, 2.48, 2.60, 2.80):
            near = min(data, key=lambda t: abs(t[0] - f))
            print(f"    {f:.2f} GHz -> {near[1]:7.2f} dB")
        print(f"  curve: {CURVE}")

REG.get("cst_quit_tool").handler()
print("\ndone")
