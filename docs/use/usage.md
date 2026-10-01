# What it looks like in use

> **Documentation index** › What it looks like in use


```text
cst_health_check_tool               {}
cst_connect_tool                    {"launch_if_needed": true}
cst_new_project_tool                {"project_type": "mws"}
cst_define_parameters_tool          {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6}}
cst_load_material_from_library_tool {"library_path": "FR-4 (lossy)", "material_name": "FR4"}
cst_create_brick_tool               {"component": "board", "name": "substrate",
                                     "xrange": ["-Lg/2","Lg/2"], "yrange": ["-Wg/2","Wg/2"],
                                     "zrange": ["-h","0"], "material": "FR4"}
cst_add_discrete_port_tool          {"port_number": 1, "point1": ["-Lg/2",0,"-h"],
                                     "point2": ["-Lg/2",0,"0.035"], "impedance": 50.0}
cst_set_solver_tool                 {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool        {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}
cst_configure_fd_solver_tool        {"mesh": "Tetrahedral", "order": "Second"}
cst_set_boundary_tool               {"all": "expanded open"}
cst_set_mesh_tool                   {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12}
cst_save_project_tool               {"path": "C:\\CST_MCP_workspace\\demo.cst"}
cst_run_solver_tool                 {}
cst_read_reference_impedance_tool   {}
cst_read_s11_tool                   {"target_frequency": 2.4}
cst_export_touchstone_tool          {"filename": "C:\\CST_MCP_workspace\\evidence\\s11"}
cst_quit_tool                       {}
```

Note there is **no meshing step**: CST 2026.2 has no VBA command that builds the mesh
on its own, so the solver does it. See *What CST 2026.2 does not expose* below.

`cst_quit_tool` at the end matters more than it looks: every open 3D project keeps a
~700 MB `modeler_AMD64.exe` alive, and leaking them is what eventually makes a solve
fail with `Not enough memory`.

Full walkthrough: **`skills/cst-studio-suite-mcp/SKILL.md`** (tool usage) and
**`skills/cst2026-simulation-execution/SKILL.md`** (verified enum values,
what counts as a trustworthy result, and troubleshooting).

---

## Related documents

* [Quick start](quickstart.md) — getting the server to answer at all
* [Rules that keep results trustworthy](rules.md) — why the call order above matters
* [Tool catalogue](tool-catalogue.md) — the full tool surface behind this session
* [What CST 2026.2 does not expose](cst-2026-limits.md) — why there is no meshing step
* [Documentation index](../README.md) — every document, grouped by task
