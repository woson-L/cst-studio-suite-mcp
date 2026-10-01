# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919-OPT1 -> inverted-F antenna (IFA) on the given feed.

Model facts (probe3.json + history):
  component1:mainpcb  Copper  x[0,100] y[0,100] z[0,1]  = ground with a 25x10 window
  antenna:antenna     Copper  x[0,25]  y[90.5,100] z[0,0.035]   <- only editable solid
  antenna:substrate   FR-4    x[0,25]  y[90,100]  z[0.035,0.965]
  the plate shares its x=25 face with mainpcb  ->  it is SHORTED to ground there
  discrete port 1 = midpoint of antenna:antenna edge 29 <-> midpoint of mainpcb edge 42,
  i.e. the 0.5 mm feed gap at x = 12.5, y 90..90.5

So the given structure is already a short-circuited plate fed 0.5 mm from ground:
keep a strip that runs from the short (x=25) through the feed (x=12.5) to an open end
(x=0) and it becomes a textbook IFA.  Only copper is removed; nothing else changes.

  strip width  SW  -> y [90.5, 90.5+SW]
  open-end trim T  -> removes x [0, T]  (tunes the resonant length 25-T)
"""
import json
import math
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

SW = float(os.environ.get("BT_SW", "2.0"))   # strip width in y (mm)
TR = float(os.environ.get("BT_TR", "0.0"))   # trim from the open end (mm)
TAG = os.environ.get("BT_TAG", f"IFA_SW{SW}_TR{TR}")

Y0, Y1, X1, ZTH = 90.5, 100.0, 25.0, 0.035
REG = mcp_server.registry
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
PROJ = RUN / "BT-20260919-OPT1.cst"


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def brief(ok, out, err, n=200):
    return (err or json.dumps(out, ensure_ascii=False, default=str))[:n]


def s11_curve(sess):
    """read_result returns rows [freq, '(<re>+<im>j)'] -> [(GHz, dB), ...]"""
    res = sess.read_result("1D Results\\S-Parameters\\S1,1", max_points=20001)
    rows = res.get("data") or []
    out = []
    for r in rows:
        if len(r) < 2:
            continue
        try:
            f = float(r[0])
        except (TypeError, ValueError):
            continue
        v = r[1]
        try:
            if isinstance(v, str):
                txt = v.strip()
                z = complex(txt) if ("j" in txt or "i" in txt) else complex(float(txt))
            else:
                z = complex(v)
        except (TypeError, ValueError):
            continue
        mag = abs(z)
        out.append((f, 20.0 * math.log10(mag) if mag > 1e-15 else -300.0))
    return out, rows


def report(tag, data, path):
    if not data:
        print("  NO DATA")
        return None
    path.write_text(json.dumps(data), encoding="utf-8")
    band = [(f, v) for f, v in data if 2.40 <= f <= 2.48]
    worst = max(band, key=lambda t: t[1]) if band else None
    best = min(data, key=lambda t: t[1])
    print(f"  [{tag}] {len(data)} pts  {data[0][0]:.4f}..{data[-1][0]:.4f} GHz")
    if worst:
        print(f"    worst 2.40-2.48 : {worst[1]:8.2f} dB @ {worst[0]:.4f} GHz"
              f"   -> {'PASS' if worst[1] <= -10 else 'FAIL'}")
    print(f"    best overall    : {best[1]:8.2f} dB @ {best[0]:.4f} GHz")
    lo = hi = None
    for f, v in data:
        if v <= -10.0:
            lo = f if lo is None else lo
            hi = f
    print(f"    S11 <= -10 dB   : {lo} .. {hi} GHz")
    for f in (2.20, 2.30, 2.40, 2.44, 2.48, 2.60, 2.80, 3.00):
        near = min(data, key=lambda t: abs(t[0] - f))
        print(f"      {f:.2f} GHz -> {near[1]:8.2f} dB")
    print(f"    saved {path.name}")
    return worst


REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(PROJ))
s = S()
for key in ("BT_AW", "BT_AH", "BT_AL"):
    os.environ.pop(key, None)


def audit_volumes():
    _, a, _ = tool("cst_model_audit_tool")
    return {sh.get("name"): (sh.get("volume"), sh.get("bbox"))
            for sh in (a or {}).get("shapes") or []}, a


print("=" * 78)
print("STEP A  baseline: the project exactly as delivered")
print("=" * 78)
v0, a0 = audit_volumes()
for k, val in v0.items():
    print(f"  {k:<24} vol={val[0]}")
print("  port x from history picks: 12.5 (plate edge 29 <-> mainpcb edge 42)")

ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  baseline solve:", "OK" if ok else "FAIL", brief(ok, out, err, 400))
if ok:
    data, raw = s11_curve(s)
    print(f"  raw first row: {raw[0] if raw else None}")
    print(f"  raw last  row: {raw[-1] if raw else None}")
    report("BASELINE", data, RUN / "s11_baseline.json")

print("\n" + "=" * 78)
print(f"STEP B  reshape into an IFA   SW={SW} mm  TR={TR} mm  tag={TAG}")
print("=" * 78)
ok, out, err = tool("cst_define_parameters_tool", parameters={"SW": SW, "TR": TR})
print("  params:", brief(ok, out, err))

strip_cut_top = Y0 + SW
cuts = [("cut_strip", ["-1", f"{X1}"], [f"{strip_cut_top}", "101"], ["-0.05", "0.1"])]
if TR > 0:
    cuts.append(("cut_trim", ["-1", f"{TR}"], ["89", "101"], ["-0.05", "0.1"]))
for name, xr, yr, zr in cuts:
    ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                        xrange=xr, yrange=yr, zrange=zr, material="PEC")
    print(f"  brick {name}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 150)}")

vb, _ = audit_volumes()
for name, *_ in cuts:
    print(f"  verify {name}: {vb.get(f'antenna:{name}', ('MISSING', None))[1]}")

for name, *_ in cuts:
    ok, out, err = tool("cst_boolean_tool", operation="subtract",
                        target="antenna:antenna", tool=f"antenna:{name}")
    print(f"  subtract {name}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 150)}")

s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
va, _ = audit_volumes()
expect = (X1 - TR) * SW * ZTH
ant = va.get("antenna:antenna", (None, None))
print(f"  antenna after cut: vol={ant[0]}  bbox={ant[1]}")
print(f"  expected          : vol={expect:.4f}  "
      f"-> {'APPLIED' if ant[0] and abs(ant[0] - expect) < 0.05 * expect else '*** NOT APPLIED ***'}")

ok, out, err = tool("cst_save_project_tool", path=str(PROJ))
print("  save:", brief(ok, out, err, 160))

ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  shaped solve:", "OK" if ok else "FAIL", brief(ok, out, err, 600))
if ok:
    data, raw = s11_curve(s)
    report(TAG, data, RUN / f"s11_{TAG}.json")

REG.get("cst_quit_tool").handler()
print("\ndone")
