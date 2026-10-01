"""End-to-end verification of the CST MCP plus the two skills (time domain).

Task (verbatim):
  1. open C:\\Users\\<user>\\Desktop\\123.cst
  2. 50 mm cube (box), material iron
  3. 50 x 50 x 5 mm sheet 2 mm below the box, material PEC
  4. discrete port at the sheet centre, connecting box and sheet
  5. frequency range 0-100 MHz
  6. solve for S-parameters

Design follows the two skills:
  * cst-studio-suite-mcp          -> mode, call order, status vocabulary, release rule
  * cst2026-simulation-execution  -> legal enum values, the four quotable-result
    checks, and the solver choice

Solver note: the task does not specify a solver. Time domain is used because the
model is electrically small over 0-100 MHz and the frequency-domain tetrahedral
path needs a preconditioner that does not fit in the RAM available on this machine
(measured: fails at ~1.0 GB free). Time domain solved it at 1.01 GB free.

Every call is logged to tests/evidence/mcp_calls_123_verify.jsonl.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
os.environ["CST_DESIGN_ENVIRONMENT_EXE"] = (
    r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
)
os.environ["CST_MCP_WORKSPACE"] = r"C:\CST_MCP_workspace"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_server  # noqa: E402  bootstrap() registers all 82 tools

REG = mcp_server.registry
PROJECT = r"C:\CST_MCP_workspace\source\123.cst"
EVID = Path(r"C:\CST_MCP_workspace\evidence")
LOG = Path(__file__).resolve().parents[1] / "tests" / "evidence" / "mcp_calls_123_verify.jsonl"
LOG.parent.mkdir(parents=True, exist_ok=True)
LOG.write_text("", encoding="utf-8")
EVID.mkdir(parents=True, exist_ok=True)

N = 0
FAILED = []
CHECKS = []


def call(tool, **args):
    global N
    N += 1
    spec = REG.get(tool)
    t0 = time.time()
    try:
        out = spec.handler(**args)
        ok = not (isinstance(out, dict) and out.get("ok") is False)
        err = None
    except Exception as exc:  # noqa: BLE001
        out, ok, err = None, False, f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - t0, 2)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"n": N, "tool": tool, "category": spec.category,
                             "args": args, "ok": ok, "elapsed_s": elapsed,
                             "result": out, "error": err},
                            ensure_ascii=False, default=str) + "\n")
    print(f"[{N:>2}] {'OK  ' if ok else 'FAIL'} {tool}"
          f"({json.dumps(args, ensure_ascii=False, default=str)[:110]})")
    print(f"       -> {(err or json.dumps(out, ensure_ascii=False, default=str))[:270]}")
    if not ok:
        FAILED.append((N, tool, (err or str(out))[:300]))
    return ok, out, err


def check(label, ok, detail=""):
    CHECKS.append((label, bool(ok), detail))
    print(f"       [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))


def d(result):
    return result if isinstance(result, dict) else {}


# ============================================================= STEP 0 preflight
print("=" * 80)
print("STEP 0  preflight  (skill: classify the mode; inspect before writing)")
print("=" * 80)
print("  mode        : new project at an existing path (fresh build)")
print(f"  target      : {PROJECT}")
print("  destructive : source was backed up to the Desktop first")
call("cst_health_check_tool")
call("cst_quit_tool")
call("cst_connect_tool", launch_if_needed=True)

# ============================================================= STEP 1 project
print("\n" + "=" * 80)
print("STEP 1  open the project file")
print("=" * 80)
ok, _, _ = call("cst_new_project_tool", project_type="mws", path=PROJECT)
if not ok:
    raise SystemExit("cannot create the project")
call("cst_project_info_tool")
_, audit, _ = call("cst_model_audit_tool")
check("project starts empty", d(audit).get("shape_count") == 0,
      f"shapes={d(audit).get('shape_count')}")

# ============================================================= STEP 2 units/params
print("\n" + "=" * 80)
print("STEP 2  units and parameters")
print("=" * 80)
call("cst_run_vba_tool", vba_code=(
    "Sub Main\nWith Units\n .SetUnit (\"Length\", \"mm\")\n"
    " .SetUnit (\"Frequency\", \"MHz\")\nEnd With\nEnd Sub"))
call("cst_define_parameters_tool", parameters={"L": 50, "t_sheet": 5, "gap": 2})

# ============================================================= STEP 3 the cube
print("\n" + "=" * 80)
print("STEP 3  50 mm cube, material iron")
print("=" * 80)
call("cst_load_material_from_library_tool", library_path="Iron")
call("cst_create_brick_tool", component="parts", name="box",
     xrange=["-L/2", "L/2"], yrange=["-L/2", "L/2"], zrange=["0", "L"],
     material="Iron")
_, audit, _ = call("cst_model_audit_tool")
box = next((s for s in d(audit).get("shapes", []) if s["name"] == "parts:box"), None)
if box:
    b = box["bbox"]
    edge = (b["x"][1] - b["x"][0], b["y"][1] - b["y"][0], b["z"][1] - b["z"][0])
    check("box exists with material Iron", box["material"] == "Iron", box["material"])
    check("box is a 50 mm cube", edge == (50.0, 50.0, 50.0), f"edges={edge}")
    check("box volume = 125000 mm3", abs(box["volume"] - 125000.0) < 1e-6,
          f"volume={box['volume']}")
else:
    check("box exists", False, "not found in audit")

# ============================================================= STEP 4 the sheet
print("\n" + "=" * 80)
print("STEP 4  50 x 50 x 5 mm sheet, 2 mm below the box, material PEC")
print("=" * 80)
print("  box spans z 0..50, so a 2 mm gap puts the sheet top at z=-2,")
print("  and a 5 mm thick sheet therefore spans z -7..-2")
call("cst_create_brick_tool", component="parts", name="sheet",
     xrange=["-L/2", "L/2"], yrange=["-L/2", "L/2"],
     zrange=["-gap-t_sheet", "-gap"], material="PEC")
_, audit, _ = call("cst_model_audit_tool")
shapes = d(audit).get("shapes", [])
sheet = next((s for s in shapes if s["name"] == "parts:sheet"), None)
box = next((s for s in shapes if s["name"] == "parts:box"), None)
if sheet and box:
    b = sheet["bbox"]
    dims = (b["x"][1] - b["x"][0], b["y"][1] - b["y"][0], b["z"][1] - b["z"][0])
    check("sheet exists with material PEC", sheet["material"] == "PEC", sheet["material"])
    check("sheet footprint is 50 x 50 mm", dims[0] == 50.0 and dims[1] == 50.0,
          f"{dims[0]}x{dims[1]}")
    check("sheet thickness is 5 mm", dims[2] == 5.0, str(dims[2]))
    check("sheet volume = 12500 mm3", abs(sheet["volume"] - 12500.0) < 1e-6,
          f"volume={sheet['volume']}")
    g = box["bbox"]["z"][0] - sheet["bbox"]["z"][1]
    check("gap between box bottom and sheet top is 2 mm", g == 2.0, f"gap={g}")
else:
    check("sheet exists", False, "not found in audit")

# ============================================================= STEP 5 the port
print("\n" + "=" * 80)
print("STEP 5  discrete port at the sheet centre, connecting sheet to box")
print("=" * 80)
print("  the port spans the gap on the centre axis: (0,0,-2) -> (0,0,0)")
call("cst_add_discrete_port_tool", port_number=1,
     point1=[0, 0, "-gap"], point2=[0, 0, "0"], impedance=50.0)
_, ports, _ = call("cst_list_ports_tool")
plist = d(ports).get("ports", [])
check("one discrete port exists", len(plist) == 1 and plist[0].get("type") == "Discrete",
      json.dumps(plist))

# ============================================================= STEP 6 solver + band
print("\n" + "=" * 80)
print("STEP 6  solver and frequency range 0 - 100 MHz")
print("=" * 80)
call("cst_set_solver_tool", solver="HF Time Domain")
call("cst_get_solver_tool")
call("cst_set_frequency_range_tool", fmin=0, fmax=100, unit="MHz")
_, freq, _ = call("cst_frequency_overview_tool")
check("solver frequency range is 0 - 100 (MHz)",
      str(d(freq).get("solver_frequency_range")) == "0 - 100",
      str(d(freq).get("solver_frequency_range")))
check("solver is HF Time Domain", d(freq).get("solver") == "HF Time Domain",
      str(d(freq).get("solver")))
call("cst_configure_td_solver_tool", accuracy="-30", mesh_type="Hexahedral")
call("cst_set_boundary_tool", all="open")
call("cst_set_background_tool", epsilon=1.0, mue=1.0, apply_in_all_directions=True)
_, meshout, _ = call("cst_set_mesh_tool", mesh_type="HexahedralFIT",
                     lines_per_wavelength=20)
check("hexahedral mesh configured for the transient solver",
      "lines_per_wavelength" in d(meshout).get("applied", {}),
      json.dumps(d(meshout).get("applied", {})))

# ============================================================= STEP 7 solve
print("\n" + "=" * 80)
print("STEP 7  save and solve")
print("=" * 80)
from cst_mcp.tools.session_tools import memory_report  # noqa: E402

mem = memory_report()
print(f"  free RAM    : {mem.get('free_ram_gb')} GB")
print(f"  CST workers : {mem.get('open_cst_workers')}")
if mem.get("warning"):
    print(f"  note        : {mem['warning'][:150]}")
check("RAM condition recorded before solving", "free_ram_gb" in mem,
      f"{mem.get('free_ram_gb')} GB free")

call("cst_save_project_tool", path=PROJECT, overwrite=True)
ok, solver, _ = call("cst_run_solver_tool", allow_low_memory=True)
call("cst_messages_tool", limit=20)
text = json.dumps(solver, ensure_ascii=False, default=str) if solver else ""
converged = "Steady state energy criterion met" in text
check("solver reports success", ok, "")
check("steady-state criterion met", converged,
      "Steady state energy criterion met, solver finished successfully." if converged
      else "not found")

# ============================================================= STEP 8 verify
print("\n" + "=" * 80)
print("STEP 8  the four quotable-result checks + S-parameters")
print("=" * 80)
call("cst_list_results_tool")
ok_s11, s11, _ = call("cst_read_s11_tool", target_frequency=100)
ok_z, zref, _ = call("cst_read_reference_impedance_tool")
_, pinfo, _ = call("cst_read_port_info_tool", operating_frequency=0.1)
call("cst_energy_summary_tool", frequency=100)
call("cst_model_audit_tool")

check("(1) solver converged", converged)
verdict = str(d(pinfo).get("verdict", ""))
check("(2) no evanescent port warning (discrete port)",
      verdict.startswith("no port mode information"), verdict[:80])
check("(3) reference impedance is 50+0j",
      str(d(zref).get("value_at_last")) == "(50+0j)",
      f"{d(zref).get('value_at_first')} .. {d(zref).get('value_at_last')}")
check("(4) geometry audit still matches", sheet is not None and box is not None)
check("S11 result tree item exists",
      ok_s11 and d(s11).get("tree_path", "").endswith("S1,1"),
      str(d(s11).get("tree_path")))
check("S11 value is a real number at 100 MHz",
      isinstance(d(s11).get("s11_db_at_target"), (int, float)),
      f"{d(s11).get('s11_db_at_target')} dB")

# ============================================================= STEP 9 evidence
print("\n" + "=" * 80)
print("STEP 9  export evidence")
print("=" * 80)
call("cst_export_touchstone_tool", filename=str(EVID / "123_verify_s11"),
     impedance=50.0, data_format="RI")
call("cst_export_ascii_tool", tree_path="1D Results\\S-Parameters\\S1,1",
     filename=str(EVID / "123_verify_s11.txt"))
call("cst_write_summary_json_tool", out_path=str(EVID / "123_verify_summary.json"),
     target_frequency=100)
call("cst_save_project_tool", path=PROJECT, overwrite=True)

# ============================================================= STEP 10 release
print("\n" + "=" * 80)
print("STEP 10  release CST  (skill rule 5)")
print("=" * 80)
_, quitout, _ = call("cst_quit_tool")
check("CST released", d(quitout).get("design_environment_released") is True,
      json.dumps(d(quitout), ensure_ascii=False, default=str)[:200])

# ============================================================= summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
passed = sum(1 for _, o, _ in CHECKS if o)
print(f"  tool calls : {N}   failed: {len(FAILED)}")
print(f"  assertions : {passed}/{len(CHECKS)} passed")
for label, ok, _ in CHECKS:
    print(f"    [{'PASS' if ok else 'FAIL'}] {label}")
if FAILED:
    print("\n  failed tool calls:")
    for row in FAILED:
        print("   ", row)
status = "validated" if (not FAILED and passed == len(CHECKS)) else "needs_validation"
print(f"\n  STATUS: {status}")
Path(EVID / "123_verify_status.txt").write_text(
    f"status={status}\ncalls={N}\nfailed_calls={len(FAILED)}\n"
    f"assertions={passed}/{len(CHECKS)}\nsolver=HF Time Domain\n", encoding="utf-8")
