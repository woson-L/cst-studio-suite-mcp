# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
"""Read-only geometry/port probe of BT-20260919-OPT1.cst.

Dumps everything needed to place the IFA cuts: solid bboxes + volumes, the port
definition, the local coordinate systems, units and solver state.  Solves
nothing and saves nothing.
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

REG = mcp_server.registry
RUN = Path(r"C:\CST_MCP_workspace\cst_runs\bt_antenna_20260919")
PROJ = RUN / "BT-20260919-OPT1.cst"
OUT = RUN / "probe3.json"


def tool(tool_name, **args):
    try:
        out = REG.get(tool_name).handler(**args)
        return out, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


REG.get("cst_quit_tool").handler()
REG.get("cst_connect_tool").handler(launch_if_needed=True)
REG.get("cst_open_project_tool").handler(path=str(PROJ))
s = S()
dump = {}

print("=" * 78)
print("1  SOLIDS")
print("=" * 78)
out, err = tool("cst_model_audit_tool")
if err:
    print("  audit failed:", err[:250])
else:
    dump["audit"] = out
    for sh in out.get("shapes") or []:
        print(f"  {sh.get('name'):<28} mat={str(sh.get('material')):<20} "
              f"vol={sh.get('volume')}")
        print(f"      {json.dumps({k: v for k, v in sh.items() if k not in ('name', 'material', 'volume')}, ensure_ascii=False, default=str)[:300]}")

print("\n" + "=" * 78)
print("2  PORTS")
print("=" * 78)
out, err = tool("cst_list_ports_tool")
if err:
    print("  list_ports failed:", err[:250])
else:
    dump["ports"] = out
    print("  " + json.dumps(out, ensure_ascii=False, default=str)[:2500])

print("\n" + "=" * 78)
print("3  PORT PROPERTIES (raw)")
print("=" * 78)
try:
    props = s.run_vba(
        "Sub Main\n"
        "Dim t As String\n"
        "On Error Resume Next\n"
        "t = t & \"impedance=\" & Port.GetImpedance(1) & vbLf\n"
        "t = t & \"type=\" & Port.GetType(1) & vbLf\n"
        "t = t & \"nports=\" & Port.GetNumberOfPorts() & vbLf\n"
        "On Error GoTo 0\n"
        "ReportInformationToWindow \"PORTQ|\" & t\n"
        "End Sub\n")
    for msg in reversed(s.messages(limit=20)):
        if msg["text"].startswith("PORTQ|"):
            print("  " + msg["text"].replace("\n", "\n  "))
            dump["portq"] = msg["text"]
            break
except Exception as exc:  # noqa: BLE001
    print("  failed:", str(exc)[:250])

print("\n" + "=" * 78)
print("4  HISTORY (names) - looking for LCS / port / antenna entries")
print("=" * 78)
try:
    m = s.model3d()
    n = m._GetHistory()
    names = []
    if isinstance(n, dict):
        entries = n.get("list") or []
        for i, e in enumerate(entries, 1):
            names.append(e.get("name") or "")
    else:
        for i in range(1, int(n) + 1):
            names.append(m.GetHistoryName(i))
    dump["history"] = names
    for i, nm in enumerate(names, 1):
        mark = ""
        low = nm.lower()
        if any(k in low for k in ("port", "coordinat", "lcs", "local")):
            mark = "   <<<<"
        print(f"  {i:>2}. {nm}{mark}")
except Exception as exc:  # noqa: BLE001
    print("  history read failed:", str(exc)[:300])

print("\n" + "=" * 78)
print("5  UNITS / SOLVER / BAND / BOUNDARY")
print("=" * 78)
for name, args in (("cst_get_parameters_tool", {}),
                   ("cst_get_solver_tool", {}),
                   ("cst_frequency_overview_tool", {}),
                   ("cst_list_monitors_tool", {})):
    out, err = tool(name, **args)
    print(f"  {name}: {err[:200] if err else json.dumps(out, ensure_ascii=False, default=str)[:600]}")
    if out is not None:
        dump[name] = out

print("\n" + "=" * 78)
print("6  ANTENNA SOLID DETAIL (faces / bbox / type)")
print("=" * 78)
try:
    vba = (
        "Sub Main\n"
        "Dim x1 As Double, x2 As Double, y1 As Double, y2 As Double, z1 As Double, z2 As Double\n"
        "On Error Resume Next\n"
        "Solid.GetBoundingBox \"antenna:antenna\", x1, x2, y1, y2, z1, z2\n"
        "ReportInformationToWindow \"BB1|\" & x1 & \"|\" & x2 & \"|\" & y1 & \"|\" & y2 & \"|\" & z1 & \"|\" & z2\n"
        "Solid.GetBoundingBox \"antenna:substrate\", x1, x2, y1, y2, z1, z2\n"
        "ReportInformationToWindow \"BB2|\" & x1 & \"|\" & x2 & \"|\" & y1 & \"|\" & y2 & \"|\" & z1 & \"|\" & z2\n"
        "Solid.GetBoundingBox \"component1:mainpcb\", x1, x2, y1, y2, z1, z2\n"
        "ReportInformationToWindow \"BB3|\" & x1 & \"|\" & x2 & \"|\" & y1 & \"|\" & y2 & \"|\" & z1 & \"|\" & z2\n"
        "On Error GoTo 0\n"
        "End Sub\n")
    s.run_vba(vba)
    for msg in reversed(s.messages(limit=30)):
        txt = msg["text"]
        if txt.startswith(("BB1|", "BB2|", "BB3|")):
            print("  " + txt.replace("\n", "\n  "))
            dump.setdefault("bbox", []).append(txt)
except Exception as exc:  # noqa: BLE001
    print("  failed:", str(exc)[:250])

OUT.write_text(json.dumps(dump, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(f"\nwritten: {OUT}")
REG.get("cst_quit_tool").handler()
print("done (nothing saved)")
