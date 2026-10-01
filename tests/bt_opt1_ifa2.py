# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""BT-20260919-OPT1 -> IFA, v2.

The project's saved WCS is rotated/moved (history entries 6..48), so Brick.Xrange/
Yrange/Zrange land in that frame.  Rather than mutate the WCS (which would also have
to replay on Rebuild), measure the frame with a probe brick and pass pre-transformed
coordinates.

Measured frame in v1:  (x, y, z)_asked -> (x+12.5, z+90.5, -y)_global
The transform is derived at run time instead of hard-coded, then verified by reading
back every brick's global bounding box.

Geometry: keep a strip  y [90.5, 90.5+SW],  x [0, 25-TR]
  - x = 25 end touches component1:mainpcb  -> the IFA short
  - discrete port 1 sits on the y = 90.5 edge at x = 12.5 -> the feed
  - x = 0 end is open -> lambda/4 resonance, tuned by TR
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

SW = float(os.environ.get("BT_SW", "2.0"))
TR = float(os.environ.get("BT_TR", "0.0"))
TAG = os.environ.get("BT_TAG", f"IFA_SW{SW}_TR{TR}")
Y0, X1, ZTH = 90.5, 25.0, 0.035

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


def report(tag, data, path):
    if not data:
        print("  NO DATA")
        return
    path.write_text(json.dumps(data), encoding="utf-8")
    band = [(f, v) for f, v in data if 2.40 <= f <= 2.48]
    best = min(data, key=lambda t: t[1])
    if band:
        w = max(band, key=lambda t: t[1])
        print(f"  worst 2.40-2.48 : {w[1]:8.2f} dB @ {w[0]:.4f} GHz  -> "
              f"{'PASS' if w[1] <= -10 else 'FAIL'}")
    print(f"  best overall    : {best[1]:8.2f} dB @ {best[0]:.4f} GHz")
    lo = hi = None
    for f, v in data:
        if v <= -10.0:
            lo = f if lo is None else lo
            hi = f
    print(f"  S11 <= -10 dB   : {lo} .. {hi} GHz")
    for f in (2.20, 2.30, 2.40, 2.44, 2.48, 2.60, 2.80):
        print(f"    {f:.2f} GHz -> {min(data, key=lambda t: abs(t[0] - f))[1]:8.2f} dB")
    print(f"  curve -> {path.name}")


# ------------------------------------------------------------------ frame probe
def measure_frame(sess):
    """Return, per asked axis, (global_axis, sign, offset) with global = sign*asked + offset.

    Two probes are needed: one brick alone cannot tell a translation from a mirror.
    """
    probes = [("wcs_probe1", (10.0, 12.0), (20.0, 23.0), (30.0, 35.0)),
              ("wcs_probe2", (110.0, 112.0), (120.0, 123.0), (130.0, 135.0))]
    got = []
    for name, xr, yr, zr in probes:
        ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                            xrange=[str(xr[0]), str(xr[1])],
                            yrange=[str(yr[0]), str(yr[1])],
                            zrange=[str(zr[0]), str(zr[1])], material="PEC")
        if not ok:
            print(f"  probe {name} failed:", brief(ok, out, err, 200))
            return None
        b = bbox_of(f"antenna:{name}")
        print(f"  {name} asked=({xr}, {yr}, {zr}) -> global {b}")
        tool("cst_delete_solid_tool", name=f"antenna:{name}")
        if not b:
            return None
        got.append(b)

    axes = "xyz"
    mapping = []
    for ax in range(3):
        a1, b1 = probes[0][1 + ax]
        a2 = probes[1][1 + ax][0]
        w = b1 - a1
        hit = [g for g in range(3)
               if abs((got[0][g][1] - got[0][g][0]) - w) < 1e-6
               and abs((got[1][g][1] - got[1][g][0]) - w) < 1e-6]
        if len(hit) != 1:
            print(f"  cannot identify axis {axes[ax]} (width {w}) -> {hit}")
            return None
        g = hit[0]
        d = (got[1][g][0] - got[0][g][0]) / (a2 - a1)
        sgn = 1.0 if d > 0 else -1.0
        off = (got[0][g][0] - a1) if sgn > 0 else (got[0][g][0] + b1)
        mapping.append((g, sgn, off))
        print(f"  asked {axes[ax]} -> global {axes[g]}  sign={sgn:+.0f} offset={off:+.4f}")
    return mapping


def inverse(mapping, want_global):
    """want_global: list of 3 (lo,hi) in global x,y,z -> ranges to pass to the tool."""
    asked = [None, None, None]
    for ax, (gaxis, sgn, off) in enumerate(mapping):
        lo, hi = want_global[gaxis]
        if sgn > 0:
            asked[ax] = (lo - off, hi - off)
        else:
            asked[ax] = (off - hi, off - lo)
    return asked


def make_cut(mapping, name, want_global):
    asked = inverse(mapping, want_global) if mapping else want_global
    ok, out, err = tool("cst_create_brick_tool", component="antenna", name=name,
                        xrange=[f"{asked[0][0]}", f"{asked[0][1]}"],
                        yrange=[f"{asked[1][0]}", f"{asked[1][1]}"],
                        zrange=[f"{asked[2][0]}", f"{asked[2][1]}"],
                        material="PEC")
    if not ok:
        print(f"  {name}: CREATE FAILED {brief(ok, out, err, 200)}")
        return False
    got = bbox_of(f"antenna:{name}")
    print(f"  {name} asked={[[round(v,4) for v in r] for r in asked]}")
    print(f"  {name} want ={[[round(v,4) for v in r] for r in want_global]}")
    print(f"  {name} got  ={[[round(v,4) for v in r] for r in (got or [])]}")
    if got is None:
        return False
    ok_box = all(abs(got[i][0] - want_global[i][0]) < 1e-4
                 and abs(got[i][1] - want_global[i][1]) < 1e-4 for i in range(3))
    print(f"  {name} position: {'OK' if ok_box else '*** WRONG ***'}")
    return ok_box


REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(PROJ))
s = S()

print("=" * 78)
print("frame probe")
print("=" * 78)
MAP = measure_frame(s)

print("\n" + "=" * 78)
print(f"build IFA   SW={SW}  TR={TR}  tag={TAG}")
print("=" * 78)
tool("cst_define_parameters_tool", parameters={"SW": SW, "TR": TR})

want = [(-1.0, X1), (Y0 + SW, 101.0), (-0.05, 0.1)]
ok1 = make_cut(MAP, "cut_strip", want)
ok2 = True
if TR > 0:
    ok2 = make_cut(MAP, "cut_trim", [(-1.0, TR), (89.0, 101.0), (-0.05, 0.1)])

if not (ok1 and ok2):
    print("\nABORT: cut bricks are not where they must be.")
    REG.get("cst_quit_tool").handler()
    sys.exit(2)

for nm in (["cut_strip"] + (["cut_trim"] if TR > 0 else [])):
    ok, out, err = tool("cst_boolean_tool", operation="subtract",
                        target="antenna:antenna", tool=f"antenna:{nm}")
    print(f"  subtract {nm}: {'ok' if ok else 'FAIL'} {brief(ok, out, err, 120)}")

s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
sh = shapes().get("antenna:antenna") or {}
expect = (X1 - TR) * SW * ZTH
vol = sh.get("volume")
print(f"  antenna after Rebuild: vol={vol} bbox={sh.get('bbox')}")
print(f"  expected             : {expect:.4f} mm^3")
applied = isinstance(vol, (int, float)) and abs(vol - expect) < 0.06 * expect
print(f"  verdict              : {'APPLIED' if applied else '*** NOT APPLIED ***'}")
if not applied:
    print("\nABORT before solving.")
    REG.get("cst_quit_tool").handler()
    sys.exit(3)

tool("cst_save_project_tool", path=str(PROJ))
print("\nsolving ...")
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if not ok:
    print("  ", str(err)[:800])
else:
    data = s11_curve(s)
    report(TAG, data, RUN / f"s11_{TAG}.json")

REG.get("cst_quit_tool").handler()
print("\ndone")
