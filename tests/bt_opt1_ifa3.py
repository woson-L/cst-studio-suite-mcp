# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919-OPT1 -> IFA v3, parameterised.

Why the shape changed: a strip running *parallel* to the 0.5 mm ground gap is a coupled
line (a 2 mm strip showed no resonance below 2.8 GHz).  A radiator has to run *away*
from the ground edge, with only a narrow short touching the ground.

Target copper inside the original plate x[0,25] y[90.5,100] z[0,0.035]:
    A  short   x[25-Wsh,25]     y[90.5, 90.5+Harm]      touches ground along x=25
    B  arm     x[Larm,25]       y[arm top +/- Warm/2]   open end at x=Larm
    C  feed    x[12.5 +/- Wfd/2] y[90.5, arm bottom]    the discrete port is at (12.5, 90.5)

The plate is only ever *cut*, so the original solid and its material stay intact.
The project's saved WCS is rotated, so every brick is created through the measured
inverse frame and its global bounding box is verified before the subtract.
"""
import json
import math
import os
import re
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

P = {k: float(os.environ.get(f"BT_{k}", d))
     for k, d in (("Larm", 3.0), ("Harm", 8.0), ("Wsh", 2.0),
                  ("Warm", 2.0), ("Wfd", 2.0))}
TAG = os.environ.get("BT_TAG", "IFA2_"
                     + "_".join(f"{k}{P[k]:g}" for k in ("Harm", "Larm", "Wsh", "Warm", "Wfd")))
Y0, XF = 90.5, 12.5

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


def shapes():
    _, a, _ = tool("cst_model_audit_tool")
    return {sh.get("name"): sh for sh in (a or {}).get("shapes") or []}


def bbox_of(name):
    sh = shapes().get(name)
    if not sh or not sh.get("bbox"):
        return None
    b = sh["bbox"]
    return [tuple(b["x"]), tuple(b["y"]), tuple(b["z"])]


def num(expr):
    """evaluate a parameter expression locally, for the verification printout"""
    e = expr
    for k, v in P.items():
        e = re.sub(rf"\b{k}\b", f"({v})", e)
    return float(eval(e))  # noqa: S307 - local constants only


def measure_frame():
    probes = [("wcs_probe1", (10.0, 12.0), (20.0, 23.0), (30.0, 35.0)),
              ("wcs_probe2", (110.0, 112.0), (120.0, 123.0), (130.0, 135.0))]
    got = []
    for name, xr, yr, zr in probes:
        ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                            xrange=[str(xr[0]), str(xr[1])],
                            yrange=[str(yr[0]), str(yr[1])],
                            zrange=[str(zr[0]), str(zr[1])], material="PEC")
        if not ok:
            print("  probe failed:", brief(ok, out, err, 200))
            return None
        b = bbox_of(f"antenna:{name}")
        tool("cst_delete_solid_tool", name=f"antenna:{name}")
        if not b:
            return None
        got.append(b)
    mapping = []
    for ax in range(3):
        a1, b1 = probes[0][1 + ax]
        a2 = probes[1][1 + ax][0]
        w = b1 - a1
        hit = [g for g in range(3)
               if abs((got[0][g][1] - got[0][g][0]) - w) < 1e-6
               and abs((got[1][g][1] - got[1][g][0]) - w) < 1e-6]
        if len(hit) != 1:
            print(f"  axis {ax} ambiguous: {hit}")
            return None
        g = hit[0]
        sgn = 1.0 if (got[1][g][0] - got[0][g][0]) / (a2 - a1) > 0 else -1.0
        off = (got[0][g][0] - a1) if sgn > 0 else (got[0][g][0] + b1)
        mapping.append((g, sgn, off))
        print(f"  asked {'xyz'[ax]} -> global {'xyz'[g]}  sign={sgn:+.0f} off={off:+.4f}")
    return mapping


def to_asked(mapping, want):
    inv = {g: (ax, sgn, off) for ax, (g, sgn, off) in enumerate(mapping)}
    out = [None, None, None]
    for g in range(3):
        ax, sgn, off = inv[g]
        lo, hi = want[g]
        o = f"{off:g}"
        out[ax] = ((f"({lo})-({o})", f"({hi})-({o})") if sgn > 0
                   else (f"({o})-({hi})", f"({o})-({lo})"))
    return out


def make_brick(mapping, name, want):
    asked = to_asked(mapping, want)
    ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                        xrange=list(asked[0]), yrange=list(asked[1]),
                        zrange=list(asked[2]), material="PEC")
    if not ok:
        print(f"  {name}: CREATE FAILED {brief(ok, out, err, 200)}")
        return False
    got = bbox_of(f"antenna:{name}")
    wantn = [[round(num(a), 4) for a in r] for r in want]
    print(f"  {name} want={wantn}")
    print(f"  {name} got ={[[round(v, 4) for v in r] for r in (got or [])]}")
    if got is None:
        return False
    okb = all(abs(got[i][0] - wantn[i][0]) < 1e-4 and abs(got[i][1] - wantn[i][1]) < 1e-4
              for i in range(3))
    print(f"  {name} {'position OK' if okb else '*** POSITION WRONG ***'}")
    return okb


def union_area(rects):
    n, total = len(rects), 0.0
    for mask in range(1, 1 << n):
        xs0 = ys0 = -1e9
        xs1 = ys1 = 1e9
        bits = 0
        for i in range(n):
            if mask >> i & 1:
                bits += 1
                x0, x1, y0, y1 = rects[i]
                xs0, ys0 = max(xs0, x0), max(ys0, y0)
                xs1, ys1 = min(xs1, x1), min(ys1, y1)
        inter = max(0.0, xs1 - xs0) * max(0.0, ys1 - ys0)
        total += inter if bits % 2 else -inter
    return total


def s11_curve(sess):
    res = sess.read_result("1D Results\\S-Parameters\\S1,1", max_points=20001)
    out = []
    for r in res.get("data") or []:
        if len(r) < 2:
            continue
        try:
            f = float(r[0])
            v = r[1]
            if isinstance(v, str):
                t = v.strip()
                z = complex(t) if ("j" in t or "i" in t) else complex(float(t))
            else:
                z = complex(v)
        except (TypeError, ValueError):
            continue
        m = abs(z)
        out.append((f, 20.0 * math.log10(m) if m > 1e-15 else -300.0))
    return out


REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(PROJ))
s = S()

print("=" * 78)
print(f"IFA v3  {TAG}")
print("=" * 78)
MAP = measure_frame()
if not MAP:
    print("frame measurement failed")
    sys.exit(2)

tool("cst_define_parameters_tool", parameters=dict(P))

Larm, Harm, Wsh, Warm, Wfd = P["Larm"], P["Harm"], P["Wsh"], P["Warm"], P["Wfd"]
GZ = ["-0.05", "0.1"]
cuts = [
    ("k_top", ["-1", "26"], [f"{Y0}+Harm", "101"], GZ),
    ("k_lft", ["-1", f"{XF}-Wfd/2"], ["90.4", f"{Y0}+Harm-Warm"], GZ),
    ("k_mid", [f"{XF}+Wfd/2", f"25-Wsh"], ["90.4", f"{Y0}+Harm-Warm"], GZ),
    ("k_end", ["-1", "Larm"], [f"{Y0}+Harm-Warm", "101"], GZ),
]
print("\ncut bricks:")
if not all(make_brick(MAP, n, w) for n, *w in cuts):
    print("\nABORT: a cut brick is misplaced.")
    REG.get("cst_quit_tool").handler()
    sys.exit(3)

for n, *_ in cuts:
    ok, out, err = tool("cst_boolean_tool", operation="subtract",
                        target="antenna:antenna", tool=f"antenna:{n}")
    print(f"  subtract {n}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 110)}")

s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
expect = union_area([(25 - Wsh, 25, Y0, Y0 + Harm),
                     (Larm, 25, Y0 + Harm - Warm, Y0 + Harm),
                     (XF - Wfd / 2, XF + Wfd / 2, Y0, Y0 + Harm - Warm)]) * 0.035
sh = shapes().get("antenna:antenna") or {}
vol = sh.get("volume")
print(f"\n  antenna after Rebuild: vol={vol} bbox={sh.get('bbox')}")
print(f"  expected             : {expect:.4f} mm^3")
okv = isinstance(vol, (int, float)) and abs(vol - expect) < 0.06 * expect
print(f"  verdict              : {'APPLIED' if okv else '*** NOT APPLIED ***'}")
if not okv:
    REG.get("cst_quit_tool").handler()
    sys.exit(4)

tool("cst_save_project_tool", path=str(PROJ))
print("\nsolving ...")
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if not ok:
    print("  ", str(err)[:700])
else:
    data = s11_curve(s)
    path = RUN / f"s11_{TAG}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    band = [(f, v) for f, v in data if 2.40 <= f <= 2.48]
    if band:
        w = max(band, key=lambda t: t[1])
        print(f"  worst 2.40-2.48: {w[1]:.2f} dB @ {w[0]:.4f} GHz -> "
              f"{'PASS' if w[1] <= -10 else 'FAIL'}")
    dips = [data[i] for i in range(1, len(data) - 1)
            if data[i][1] < data[i - 1][1] and data[i][1] <= data[i + 1][1]
            and data[i][1] < -3]
    print("  local minima < -3 dB:",
          ", ".join(f"{v:.1f}dB@{f:.3f}GHz" for f, v in dips[:8]) or "none")
    b = min(data, key=lambda t: t[1])
    print(f"  best {b[1]:.2f} dB @ {b[0]:.4f} GHz")
    for f in (1.8, 2.0, 2.2, 2.4, 2.44, 2.48, 2.6, 2.8, 3.0):
        print(f"    {f:.2f} GHz -> {min(data, key=lambda t: abs(t[0] - f))[1]:7.2f} dB")
    print(f"  curve -> {path.name}")

REG.get("cst_quit_tool").handler()
print("\ndone")
