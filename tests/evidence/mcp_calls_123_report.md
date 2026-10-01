# Worked task on 123.cst — MCP tool-call record

**30** MCP tool calls, **0** failures.

| # | MCP tool | Category | Key arguments | Result | Time (s) |
|---|---|---|---|---|---|
| 1 | `cst_quit_tool` | Session / project | `{}` | {"ok": true, "closed_projects": [], "failed_projects": [], "design_environment_released": true} | 6.69 |
| 2 | `cst_health_check_tool` | Session / project | `{}` | {"cst_install_root": "C:\\Program Files\\CST Studio Suite 2026", "cst_exe": "C:\\Program Files\\CST Studio Sui... | 0.08 |
| 3 | `cst_connect_tool` | Session / project | `{"launch_if_needed": true}` | {"connected": true, "design_environment_pid": 21828, "has_active_project": false, "open_projects": [], "active... | 1.44 |
| 4 | `cst_new_project_tool` | Session / project | `{"project_type": "mws", "path": "C:\\Users\\<user>\\Desktop\\123.cst"}` | {"connected": true, "design_environment_pid": 21828, "has_active_project": true, "open_projects": ["C:\\Users\... | 4.84 |
| 5 | `cst_run_vba_tool` | Session / project | `{"vba_code": "Sub Main\nWith Units\n .SetUnit (\"Length\", \"mm\")\n .SetUnit (\"Frequency\", \"MHz\")\nEnd With\nEnd...` | {"ok": true, "messages_tail": []} | 0.04 |
| 6 | `cst_define_parameters_tool` | Parameters | `{"parameters": {"L": 50, "gap": 2, "tsheet": 5}}` | {"ok": true, "changed": {"L": "50", "gap": "2", "tsheet": "5"}, "method": "parameter list (MakeSureParameterEx... | 0.53 |
| 7 | `cst_load_material_from_library_tool` | Material | `{"library_path": "Iron"}` | {"ok": true, "title": "load material Iron from library", "library_path": "Iron", "material": "Iron", "library_... | 0.16 |
| 8 | `cst_create_brick_tool` | Geometry | `{"component": "parts", "name": "box", "xrange": ["-L/2", "L/2"], "yrange": ["-L/2", "L/2"], "zrange": ["0", "L"], "ma...` | {"ok": true, "title": "create brick parts:box", "solid": "parts:box"} | 0.07 |
| 9 | `cst_model_audit_tool` | Verify | `{}` | {"ok": true, "shape_count": 1, "shapes": [{"name": "parts:box", "material": "Iron", "volume": 125000.0, "bbox"... | 0.03 |
| 10 | `cst_create_brick_tool` | Geometry | `{"component": "parts", "name": "sheet", "xrange": ["-L/2", "L/2"], "yrange": ["-L/2", "L/2"], "zrange": ["-gap-tsheet...` | {"ok": true, "title": "create brick parts:sheet", "solid": "parts:sheet"} | 0.03 |
| 11 | `cst_model_audit_tool` | Verify | `{}` | {"ok": true, "shape_count": 2, "shapes": [{"name": "parts:box", "material": "Iron", "volume": 125000.0, "bbox"... | 0.02 |
| 12 | `cst_add_discrete_port_tool` | Port / excitation | `{"port_number": 1, "point1": [0, 0, "-gap"], "point2": [0, 0, "0"], "impedance": 50.0}` | {"ok": true, "port_number": 1, "type": "discrete", "impedance": 50.0} | 0.02 |
| 13 | `cst_list_ports_tool` | Port / excitation | `{}` | {"ok": true, "count": 1, "ports": [{"port_number": 1, "type": "Discrete", "modes": 0}]} | 0.01 |
| 14 | `cst_set_solver_tool` | Solver / band | `{"solver": "HF Frequency Domain"}` | {"ok": true, "requested": "HF Frequency Domain", "solver": "HF Frequency Domain"} | 0.12 |
| 15 | `cst_get_solver_tool` | Solver / band | `{}` | {"ok": true, "solver": "HF Frequency Domain"} | 0.01 |
| 16 | `cst_set_frequency_range_tool` | Solver / band | `{"fmin": 0, "fmax": 100, "unit": "MHz"}` | {"ok": true, "frequency_range": [0, 100], "unit": "MHz", "unit_applied": true, "previous_unit": "GHz"} | 0.19 |
| 17 | `cst_frequency_overview_tool` | Solver / band | `{}` | {"ok": true, "solver": "HF Frequency Domain", "solver_frequency_range": "0 - 100", "monitors": [], "note": "so... | 0.04 |
| 18 | `cst_configure_fd_solver_tool` | Solver / band | `{"mesh": "Tetrahedral", "sweep": "General Purpose", "order": "Second", "accuracy": "1e-4"}` | {"ok": true, "applied": {"mesh": "Tetrahedral", "sweep": "General Purpose", "order_tet": "Second", "accuracy_t... | 0.01 |
| 19 | `cst_set_background_tool` | Solver / band | `{"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": true}` | {"ok": true, "epsilon": 1.0, "mue": 1.0} | 0.04 |
| 20 | `cst_set_boundary_tool` | Solver / band | `{"xmin": "open", "xmax": "open", "ymin": "open", "ymax": "open", "zmin": "open", "zmax": "open"}` | {"ok": true, "boundaries": {"xmin": "open", "xmax": "open", "ymin": "open", "ymax": "open", "zmin": "open", "z... | 0.89 |
| 21 | `cst_set_mesh_tool` | Mesh | `{"mesh_type": "Tetrahedral", "steps_per_wavelength": 8}` | {"ok": true, "applied": {"mesh_type": "Tetrahedral", "steps_per_wavelength_tet": 8}} | 0.05 |
| 22 | `cst_save_project_tool` | Session / project | `{"path": "C:\\Users\\<user>\\Desktop\\123.cst", "overwrite": true}` | {"ok": true, "path": "C:\\Users\\<user>\\Desktop\\123.cst", "overwritten": false, "note": "already the active p... | 0.77 |
| 23 | `cst_run_solver_tool` | Solver / band | `{}` | {"ok": true, "messages_tail": [{"type": "INFO", "text": "Excitation: port 1"}, {"type": "INFO", "text": "All b... | 2.77 |
| 24 | `cst_messages_tool` | Session / project | `{"limit": 20}` | {"ok": true, "count": 20, "messages": [{"type": "INFO", "text": "Please prefer discrete face ports over discre... | 0.0 |
| 25 | `cst_list_results_tool` | Results | `{}` | {"ok": true, "count": 22, "items": ["1D Results\\Balance\\Balance [1]", "1D Results\\Convergence\\Equation Sys... | 0.0 |
| 26 | `cst_read_s11_tool` | Verify | `{"target_frequency": 100}` | {"ok": true, "tree_path": "1D Results\\S-Parameters\\S1,1", "target_frequency": 100.0, "s11_db_at_target": -1.... | 0.02 |
| 27 | `cst_read_reference_impedance_tool` | Verify | `{}` | {"ok": true, "value_at_first": "(50+0j)", "value_at_last": "(50+0j)", "length": 1002} | 0.01 |
| 28 | `cst_energy_summary_tool` | Verify | `{"frequency": 100}` | {"ok": true, "frequency": 100, "power_accepted": 0.13053752720612447, "power_stimulated": 0.5, "loss_dielectri... | 0.02 |
| 29 | `cst_export_touchstone_tool` | Export | `{"filename": "C:\\CST_MCP_workspace\\evidence\\123_s11", "impedance": 50.0, "data_format": "RI"}` | {"ok": true, "filename": "C:\\CST_MCP_workspace\\evidence\\123_s11", "written": ["C:\\CST_MCP_workspace\\evide... | 0.27 |
| 30 | `cst_export_ascii_tool` | Export | `{"tree_path": "1D Results\\S-Parameters\\S1,1", "filename": "C:\\CST_MCP_workspace\\evidence\\123_s11.txt"}` | {"ok": true, "filename": "C:\\CST_MCP_workspace\\evidence\\123_s11.txt", "exists": true, "mode_note": "request... | 0.27 |

## MCP tools used (28 distinct)

- `cst_add_discrete_port_tool`
- `cst_configure_fd_solver_tool`
- `cst_connect_tool`
- `cst_create_brick_tool`  ×2
- `cst_define_parameters_tool`
- `cst_energy_summary_tool`
- `cst_export_ascii_tool`
- `cst_export_touchstone_tool`
- `cst_frequency_overview_tool`
- `cst_get_solver_tool`
- `cst_health_check_tool`
- `cst_list_ports_tool`
- `cst_list_results_tool`
- `cst_load_material_from_library_tool`
- `cst_messages_tool`
- `cst_model_audit_tool`  ×2
- `cst_new_project_tool`
- `cst_quit_tool`
- `cst_read_reference_impedance_tool`
- `cst_read_s11_tool`
- `cst_run_solver_tool`
- `cst_run_vba_tool`
- `cst_save_project_tool`
- `cst_set_background_tool`
- `cst_set_boundary_tool`
- `cst_set_frequency_range_tool`
- `cst_set_mesh_tool`
- `cst_set_solver_tool`

---

## Related documents

* [Failures hit during development](known_failures.md) — the raw CST errors behind the pitfalls this run worked around
* [Verification](../../docs/dev/verification.md) — how this run fits with the rest of the committed evidence
* [Worked example and verification status](../../skills/cst2026-simulation-execution/references/worked-example.md) — the same task written up as a reusable recipe
* [Tool catalogue](../../docs/use/tool-catalogue.md) — every tool these 30 calls are drawn from, by category
* [Documentation index](../../docs/README.md) — the grouped index of the whole documentation set
