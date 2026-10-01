# Worked example and verification status

## Minimal end-to-end reference

A microstrip patch on FR-4 fed by a discrete port, 2.0–3.0 GHz. Copy and adapt.

```text
cst_health_check_tool          {}
cst_connect_tool               {"launch_if_needed": true}
cst_new_project_tool           {"project_type": "mws"}
cst_define_parameters_tool     {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6, "tcond": 0.035}}
cst_load_material_from_library_tool {"library_path": "FR-4 (lossy)", "material_name": "FR4"}
cst_create_brick_tool          {"component": "board", "name": "substrate",
                                "xrange": ["-Lg/2","Lg/2"], "yrange": ["-Wg/2","Wg/2"],
                                "zrange": ["-h","0"], "material": "FR4"}
cst_create_brick_tool          {"component": "board", "name": "ground",
                                "xrange": ["-Lg/2","Lg/2"], "yrange": ["-Wg/2","Wg/2"],
                                "zrange": ["-h-tcond","-h"], "material": "PEC"}
cst_add_discrete_port_tool     {"port_number": 1, "point1": ["-Lg/2",0,"-h"],
                                "point2": ["-Lg/2",0,"tcond"], "impedance": 50.0}
cst_set_solver_tool            {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool   {"fmin": 2.0, "fmax": 3.0, "unit": "GHz"}
cst_configure_fd_solver_tool   {"mesh": "Tetrahedral", "order": "Second", "accuracy": "1e-4"}
cst_set_boundary_tool          {"all": "expanded open"}
cst_set_background_tool        {"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": true}
cst_set_mesh_tool              {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12}
cst_save_project_tool          {"path": "C:\\CST_MCP_workspace\\demo.cst"}
cst_run_solver_tool            {}
cst_read_reference_impedance_tool     # expect 50+0j on a discrete 50 ohm port
cst_read_s11_tool              {"target_frequency": 2.4}
cst_export_touchstone_tool     {"filename": "C:\\CST_MCP_workspace\\evidence\\s11"}
cst_quit_tool                  {}
```

Note the two things that are **absent on purpose**: there is no meshing step (the
solver meshes), and there is no verification of the result here — do that with the
four checks in `solve-verify-evidence.md`.

Then report: solver, band, reference impedance, S11 at the target frequency, best S11
and its frequency, the bandwidth around the target, efficiency, and the paths of the
exported files — plus anything that failed, with the CST error text.

## A worked task with real numbers

For a complete, measured example (50 mm iron cube 2 mm above a 50 × 50 × 5 mm PEC
sheet, discrete port across the gap, 0–100 MHz) see `tests/run_123_task.py` and
`tests/evidence/mcp_calls_123_report.md` in the CST-MCP package. Measured result:

```
converged: 5 frequency samples, "All broadband sweep convergence criteria have been satisfied"
S11 @ 100 MHz = -1.314 dB     (1002 points, -1.3115 -> -1.3140 dB across the band)
ZRef = (50+0j)
power: stimulated 0.5 / accepted 0.1305 / metal loss 1.53e-4
```

S11 ≈ −1.31 dB and nearly flat is **physically correct** here: a 2 mm air gap is
electrically almost zero at a 3 m wavelength, so the port sees a near short — almost
total reflection, not a resonance.

That task also needs `smallest_feature_mm: 2.0`; without it the solve stops at
`Could not compute preconditioner.` See `ports-boundaries-mesh.md`.

## Verification status of this skill

The enum values, command strings and error texts here come from live runs of the CST
MCP against **CST Studio Suite 2026.2**:

| Evidence | Result |
| --- | --- |
| `tests/verify_live.py` full chain (incl. real solve) | 82/82 |
| `tests/verify_fixes_live.py` targeted tool verification | 28/28 |
| `tests/run_123_task.py` worked task | 30 calls, 0 failed |
| `tests/test_audit_regressions.py` | 63/63 |
| `tests/test_port_info_verdict.py` | 13/13 |
| `tests/check_mcp_compliance.py` | 17/17 |

Raw logs, exported S-parameters and the recorded failures are in
`tests/evidence/` — read `known_failures.md` there first when diagnosing.

When a CST upgrade changes a message or a method name, prefer re-probing over trusting
this text: run `tests/probe_commands.py`, which exercises individual CST VBA commands
and reports exactly which ones the installed build accepts.

---

## Related documents

* [Solve, verify, evidence](solve-verify-evidence.md) — the four checks this example leaves out
* [Ports, boundaries and mesh](ports-boundaries-mesh.md) — why smallest_feature_mm is needed here
* [Solver selection and band](solver-and-band.md) — the solver and band settings used above
* [Starting templates](../../cst-studio-suite-mcp/references/templates.md) — the template this sequence adapts
* [Verification](../../../docs/dev/verification.md) — how to reproduce these runs
