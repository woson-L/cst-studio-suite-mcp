# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Create BT-20260919-OPT1.cst and establish the baseline.

Answers three things at once:
  1. where in the model the given port actually sits (does the source model solve at all);
  2. whether Solid.Subtract genuinely changes the antenna (the earlier run said no);
  3. what S11 looks like at the given starting shape.
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
DESK = Path(r"C:\CST_MCP_workspace\source")
SRC = next((p for p in (DESK / "BT-20260919-OPT1.cst", DESK / "BT-20260919.cst")
            if p.is_file()), None)
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
RUN.mkdir(parents=True, exist_ok=True)
OPT = RUN / "BT-20260919-OPT1.cst"

print(f"source: {SRC}")


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


def brief(ok, out, err):
    return (err or json.dumps(out, ensure_ascii=False, default=str))[:170]


print("=" * 78)
print("STEP 1  create BT-20260919-OPT1.cst as a copy of the source")
print("=" * 78)
REG.get("cst_quit_tool").handler()
for p in (OPT, OPT.with_suffix("")):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.is_file():
        p.unlink()
shutil.copy2(SRC, OPT)
if SRC.with_suffix("").is_dir():
    shutil.copytree(SRC.with_suffix(""), OPT.with_suffix(""))
print(f"  {OPT.name} created ({OPT.stat().st_size} B)")

REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(OPT))
s = S()

print("\n" + "=" * 78)
print("STEP 2  BASELINE: solve the model exactly as given (no geometry change)")
print("=" * 78)
print("  ", brief(*tool("cst_save_project_tool", path=str(OPT))))
ok, out, err = tool("cst_run_solver_tool", allow_low_memory=True)
print("  solve:", "OK" if ok else "FAIL")
if err:
    for line in str(err).splitlines():
        if any(k in line for k in ("ERROR", "WARNING", "Staircas", "port")):
            print("   ", line.strip()[:170])
else:
    for m in (out.get("messages_tail") or [])[:5]:
        print("   ", str(m)[:150])

if ok:
    ok2, z, _ = tool("cst_read_reference_impedance_tool")
    print("  ZRef:", brief(ok2, z, None))
    try:
        res = s.read_result("1D Results\\S-Parameters\\S1,1", max_points=10001)
        data = [(float(r[0]), r[1]) for r in (res.get("data") or []) if len(r) > 1]
        band = [(f, v) for f, v in data if 2.40 <= f <= 2.48]
        print(f"  curve points: {len(data)}, in band: {len(band)}")
        if band:
            w = max(band, key=lambda t: t[1])
            print(f"  worst in 2.40-2.48: {w[1]:.3f} dB at {w[0]:.4f} GHz"
                  f"  -> {'PASS' if w[1] <= -10 else 'FAIL'}")
        if data:
            bb = min(data, key=lambda t: t[1])
            print(f"  overall best: {bb[1]:.3f} dB at {bb[0]:.4f} GHz")
    except Exception as exc:  # noqa: BLE001
        print("  curve read failed:", str(exc)[:200])

print("\n" + "=" * 78)
print("STEP 3  does Solid.Subtract really change the antenna?")
print("=" * 78)
_, audit, _ = tool("cst_model_audit_tool")
ant_before = next((sh["volume"] for sh in (audit.get("shapes") or [])
                   if sh["name"] == "antenna:antenna"), None)
print(f"  antenna volume now: {ant_before}")

# unambiguous cut: remove the whole left half of the antenna sheet
tool("cst_create_brick_tool", component="antenna", name="probe_cut",
     xrange=["0", "12"], yrange=["89", "101"], zrange=["0.03", "0.97"], material="PEC")
ok, out, err = tool("cst_boolean_tool", operation="subtract",
                    target="antenna:antenna", tool="antenna:probe_cut")
print("  subtract half:", "OK" if ok else "FAIL", str(out or err)[:120])
s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
_, audit2, _ = tool("cst_model_audit_tool")
for sh in audit2.get("shapes") or []:
    print(f"    {sh['name']:<26} vol={sh['volume']}")
ant_after = next((sh["volume"] for sh in (audit2.get("shapes") or [])
                  if sh["name"] == "antenna:antenna"), None)
print(f"  -> volume {ant_before} => {ant_after}: "
      f"{'SUBTRACT WORKS' if ant_after != ant_before else 'SUBTRACT DOES NOTHING'}")

print("\n  (this cut is NOT saved - the project is discarded)")
REG.get("cst_quit_tool").handler()
print("done")
