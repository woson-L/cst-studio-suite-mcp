# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Inspect BT-20260919-OPT1.cst: the given port, the antenna shape, and the history.

Resolves the open question from the previous attempt: Solid.Subtract was recorded but
the copper volume never changed and the port reported "completely inside metal".
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
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
RUN.mkdir(parents=True, exist_ok=True)

# find the source, wherever the user put it
cands = [DESK / "BT-20260919-OPT1.cst", DESK / "BT-20260919.cst"]
src = next((p for p in cands if p.is_file()), None)
print("candidates:")
for p in cands:
    print(f"   {'FOUND ' if p.is_file() else '      '} {p}")
if src is None:
    raise SystemExit("no source project found")
print(f"\nsource: {src}  ({src.stat().st_size} B, {src.stat().st_mtime})")

WORK = RUN / "BT-20260919-OPT1.cst"
REG.get("cst_quit_tool").handler()
for p in (WORK, WORK.with_suffix("")):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.is_file():
        p.unlink()
shutil.copy2(src, WORK)
if src.with_suffix("").is_dir():
    shutil.copytree(src.with_suffix(""), WORK.with_suffix(""))
print(f"working copy: {WORK}")

REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(WORK))
s = S()


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return not (isinstance(out, dict) and out.get("ok") is False), out, None
    except Exception as exc:  # noqa: BLE001
        return False, None, f"{type(exc).__name__}: {exc}"


print("\n" + "=" * 78)
print("A. parameters")
print("=" * 78)
_, par, _ = tool("cst_get_parameters_tool")
for k, v in (par.get("parameters") or {}).items():
    print(f"   {k:<16} = {v}")
if not par.get("parameters"):
    print("   (none)")

print("\n" + "=" * 78)
print("B. solids")
print("=" * 78)
_, audit, _ = tool("cst_model_audit_tool")
for sh in audit.get("shapes") or []:
    b = sh["bbox"]
    print(f"   {sh['name']:<26} mat={sh['material']:<18} vol={sh['volume']:<12}")
    print(f"       x={b['x']}  y={b['y']}  z={b['z']}")

print("\n" + "=" * 78)
print("C. ports (the given discrete port)")
print("=" * 78)
_, ports, _ = tool("cst_list_ports_tool")
print("   ", json.dumps(ports, ensure_ascii=False, default=str))

print("\n" + "=" * 78)
print("D. history: the model's own record")
print("=" * 78)
try:
    hist = s.model3d()._GetHistory()
    entries = hist["list"] if isinstance(hist, dict) else hist
    print(f"   entries: {len(entries)}")
    for i, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            continue
        nm = str(e.get("name", "?"))
        if any(k in nm.lower() for k in
               ("brick", "subtract", "add shapes", "port", "slice", "rebuild",
                "rename", "change component", "change material", "new component")):
            print(f"\n   --- {i}. {nm}   error={e.get('error')} exclude={e.get('exclude')}")
            for line in str(e.get("contents", "")).splitlines():
                print(f"         {line}")
except Exception as exc:  # noqa: BLE001
    print("   history read failed:", str(exc)[:250])

print("\n" + "=" * 78)
print("E. does the copper volume respond to a cut at all?  (sanity probe)")
print("=" * 78)
# Take the volume before and after subtracting a big, unambiguous block.
before = next((sh["volume"] for sh in (audit.get("shapes") or [])
               if sh["name"] == "antenna:antenna"), None)
print(f"   antenna volume before: {before}")
probe_ok, probe_out, probe_err = tool("cst_create_brick_tool",
                                      component="antenna", name="probe_cut",
                                      xrange=["0", "25"], yrange=["90", "95"],
                                      zrange=["0.965", "1.0"], material="PEC")
print(f"   create probe brick: {probe_ok} {str(probe_out or probe_err)[:120]}")
if probe_ok:
    ok2, out2, err2 = tool("cst_boolean_tool", operation="subtract",
                           target="antenna:antenna", tool="antenna:probe_cut")
    print(f"   subtract half the block: {ok2} {str(out2 or err2)[:140]}")
    s.run_vba("Sub Main\nRebuild\nEnd Sub\n")
    _, audit2, _ = tool("cst_model_audit_tool")
    after = next((sh["volume"] for sh in (audit2.get("shapes") or [])
                  if sh["name"] == "antenna:antenna"), None)
    print(f"   antenna volume after : {after}")
    print(f"   -> subtraction {'WORKS' if after != before else 'DOES NOTHING'}")
    # is the solid even still named the same / still present?
    names = [sh["name"] for sh in (audit2.get("shapes") or [])]
    print(f"   solids now: {names}")

print("\n   NOTE: the probe cut is discarded - this project is not saved.")
REG.get("cst_quit_tool").handler()
print("\ndone (nothing saved)")
