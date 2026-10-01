"""Targeted live check of the tools changed by this bug-fix round.

Deliberately does NOT run the solver: the machine had only ~1.7 GB free and a
frequency-domain solve dies with "Not enough memory". This checks that every
changed VBA block is accepted by real CST 2026.2 and that the reads return sane
values.
"""
import os
import sys
import tempfile

os.environ["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
os.environ["CST_DESIGN_ENVIRONMENT_EXE"] = (
    r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
)
os.environ["CST_MCP_WORKSPACE"] = str(Path(tempfile.gettempdir()) / "cst_mcp_verify" / "workspace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_server  # noqa: E402,F401  - bootstrap registers the tools
from cst_mcp.session import session  # noqa: E402

REG = mcp_server.registry
PASS, FAIL = [], []


def run(label, tool, args):
    try:
        out = REG.get(tool).handler(**args)
        print(f"[PASS] {label}")
        print(f"       -> {str(out)[:300]}")
        PASS.append(label)
        return True, out
    except Exception as exc:
        print(f"[FAIL] {label}\n       {type(exc).__name__}: {str(exc)[:300]}")
        FAIL.append(label)
        return False, exc


def rejected(label, tool, args, want):
    try:
        out = REG.get(tool).handler(**args)
        print(f"[FAIL] {label}: accepted but should be rejected -> {str(out)[:160]}")
        FAIL.append(label)
    except Exception as exc:
        ok = want.lower() in str(exc).lower()
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        print(f"       rejected with: {str(exc)[:220]}")
        (PASS if ok else FAIL).append(label)


s = session()
print("connected:", s.connect(launch_if_needed=True).get("connected"))
info = s.new_project(project_type="mws")
print("project:", (info.get("active_project") or {}).get("filename"))
print()

print("=== A. frequency range now applies the unit ===")
run("freq range GHz", "cst_set_frequency_range_tool",
    {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"})
unit = run("frequency_overview reads the band back", "cst_frequency_overview_tool", {})[1]
if unit and unit.get("solver_frequency_range") != "2.2 - 2.7":
    print(f"       WARNING: band is {unit.get('solver_frequency_range')!r}, expected '2.2 - 2.7'")
    FAIL.append("band-after-unit-change")
else:
    PASS.append("band-after-unit-change")
rejected("unknown unit refused", "cst_set_frequency_range_tool",
         {"fmin": 1, "fmax": 2, "unit": "furlongs"}, "unknown frequency unit")

print("\n=== B. background uses the documented Reset/Mu ===")
run("set_background epsilon/mue", "cst_set_background_tool",
    {"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": True})

print("\n=== C. boundary allow-list and casing ===")
run("boundary expanded open", "cst_set_boundary_tool", {"all": "expanded open"})
run("boundary folded casing 'Electric'", "cst_set_boundary_tool", {"all": "Electric"})
run("boundary restored", "cst_set_boundary_tool", {"all": "expanded open"})
run("boundary 'tangential' now accepted", "cst_set_boundary_tool", {"all": "tangential"})
run("boundary restored again", "cst_set_boundary_tool", {"all": "expanded open"})
rejected("boundary 'none' refused", "cst_set_boundary_tool", {"all": "none"},
         "not a known boundary kind")

print("\n=== D. FD solver enum fixes ===")
run("set HF Frequency Domain", "cst_set_solver_tool", {"solver": "HF Frequency Domain"})
run("fd order Third (tet)", "cst_configure_fd_solver_tool",
    {"mesh": "Tetrahedral", "order": "Third", "accuracy": "1e-4"})
run("fd order Mixed -> MixedOrderTet", "cst_configure_fd_solver_tool",
    {"mesh": "Tetrahedral", "order": "Mixed", "accuracy": "1e-4"})
run("fd hexahedral numeric accuracy 1e-5", "cst_configure_fd_solver_tool",
    {"mesh": "Hexahedral", "sweep": "General Purpose", "accuracy": "1e-5"})
run("fd hexahedral alias High -> 1e-5", "cst_configure_fd_solver_tool",
    {"mesh": "Hexahedral", "accuracy": "High"})
rejected("fd out-of-range accuracy refused", "cst_configure_fd_solver_tool",
         {"mesh": "Hexahedral", "accuracy": "0.5"}, "outside the range")
rejected("fd mesh_adaption on hexahedral refused", "cst_configure_fd_solver_tool",
         {"mesh": "Hexahedral", "mesh_adaption": True}, "tetrahedral")
run("fd back to the working tetrahedral config", "cst_configure_fd_solver_tool",
    {"mesh": "Tetrahedral", "sweep": "General Purpose", "order": "Second", "accuracy": "1e-4"})

print("\n=== E. eigenmode method/mesh pairing ===")
run("set HF Eigenmode", "cst_set_solver_tool", {"solver": "HF Eigenmode"})
run("eigenmode AKS on Hexahedral -> \"Hex\"", "cst_configure_eigenmode_solver_tool",
    {"n_modes": 2, "mesh_type": "Hexahedral Mesh", "method": "AKS"})
run("eigenmode General (Lossy) on Tetrahedral -> \"Tet\"",
    "cst_configure_eigenmode_solver_tool",
    {"n_modes": 2, "mesh_type": "Tetrahedral Mesh", "method": "General (Lossy)"})
rejected("eigenmode AKS on Tetrahedral refused", "cst_configure_eigenmode_solver_tool",
         {"n_modes": 2, "mesh_type": "Tetrahedral Mesh", "method": "AKS"}, "not valid")
rejected("eigenmode JDM still refused", "cst_configure_eigenmode_solver_tool",
         {"n_modes": 2, "mesh_type": "Hexahedral Mesh", "method": "JDM"}, "not valid")

print("\n=== F. library material is renamed as requested ===")
ok, out = run("load FR-4 as MCP_FR4_LIVE", "cst_load_material_from_library_tool",
              {"library_path": "FR-4 (lossy)", "material_name": "MCP_FR4_LIVE"})
exists = False
if ok:
    try:
        session().run_vba(
            "Sub Main\nDim n As Long, i As Long, s As String\n"
            "On Error Resume Next\nn = Material.GetNumberOfMaterials()\nOn Error GoTo 0\n"
            's = ""\nFor i = 0 To n - 1\n'
            's = s & Material.GetNameOfMaterialFromIndex(i) & ";"\nNext i\n'
            'ReportInformationToWindow "MCPSETF=" & s\nEnd Sub\n'
        )
        for m in reversed(session().messages(limit=8)):
            if "MCPSETF=" in m["text"]:
                listing = m["text"].split("MCPSETF=", 1)[1]
                print("       materials in project:", listing)
                exists = "MCP_FR4_LIVE" in listing
                break
    except Exception as exc:
        print("       listing failed:", str(exc)[:120])
print(f"[{'PASS' if exists else 'FAIL'}] MCP_FR4_LIVE really exists in the project")
(PASS if exists else FAIL).append("material rename persisted")

print("\n=== G. backslash library path is split correctly ===")
# Load only, without a rename: section F already renamed "FR-4 (lossy)" away, and
# re-loading it under the same library leaf would make Material.Rename fail for a
# reason unrelated to the path handling being tested here.
ok, out = run("load with a backslash path", "cst_load_material_from_library_tool",
              {"library_path": "Substrates\\FR-4 (lossy)"})
correct = bool(ok
               and out.get("library_path") == "Substrates/FR-4 (lossy)"
               and out.get("library_material") == "FR-4 (lossy)")
print(f"[{'PASS' if correct else 'FAIL'}] the backslash path resolved to folder+leaf")
print("       path=%r leaf=%r folder=%r" % (out.get("library_path") if ok else None,
                                            out.get("library_material") if ok else None,
                                            out.get("folder") if ok else None))
(PASS if correct else FAIL).append("backslash library path")

print(f"\n==== targeted live check: {len(PASS)} passed, {len(FAIL)} failed ====")
if FAIL:
    print("failed:", FAIL)
s.close_project()
sys.exit(0 if not FAIL else 1)
