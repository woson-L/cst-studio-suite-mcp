# Tool catalogue and call order

The server exposes **82 tools** across 13 categories. Machine-readable companion:
`docs/mcp_tools.json` — every tool with its parameters, JSON schema, examples and
notes. Read that file when you need an exact signature; read this file when you need
the *order*.

Discover the live surface at runtime:
`cst_list_mcp_tools_tool` (optionally `{"category": "geometry"}`).
Write the manifest for another agent: `cst_tool_manifest_tool {"out_path": "..."}`.

## Categories

| Category | Tools | Purpose |
| --- | --- | --- |
| `session` | 14 | health, detect, connect, projects, messages, raw VBA, history blocks, release |
| `parameters` | 4 | read, create, change, delete design parameters |
| `geometry` | 14 | brick, cylinder, sphere, cone, torus, ECylinder, bondwire, boolean, transform, extrude, component |
| `material` | 3 | create, assign, load from library (with rename) |
| `port` | 3 | discrete port, waveguide port, list ports |
| `solver` | 11 | solver choice, frequency range (unit-aware), FD/TD/eigenmode config, boundary, symmetry, background, run |
| `mesh` | 2 | mesh type and density. **No mesh-generation tool** — see below |
| `monitor` | 2 | add and list field monitors |
| `results` | 2 | list result tree, read a 1D item |
| `verify` | 5 | S11, reference impedance, port info (with verdict), energy budget, model audit |
| `export` | 3 | Touchstone, ASCII, summary JSON |
| `runtime` | 16 | built-in command bridge + typed wrapper generation (8 implementations, dual aliases) |
| `meta` | 3 | list tools, full manifest, dynamic dispatch |

## Call order

Each step can be retried independently.

### Step 0 — environment

```
cst_health_check_tool     # ready flag + resources: free RAM and live CST worker count
cst_detect_tool           # install path, executable, running Design Environments
```

If `ready` is false, the `.env` beside `mcp_server.py` has the wrong
`CST_INSTALL_ROOT` / `CST_DESIGN_ENVIRONMENT_EXE`. Ask the operator to run
`python check_install.py --fix`, which locates the CST installation on the machine and
rewrites `.env`; `python check_install.py --list-installs` shows what it would choose.
Do not try to set those paths from inside a CST tool call — they are read at server
start-up.

If the MCP server is not reachable at all, the same script diagnoses it without needing
CST: `python check_install.py --quick` checks Python, the `mcp` package, the server
files and the tool registry; the full `python check_install.py` adds an MCP handshake
with `tools/list` and a live CST connection test.

`cst_health_check_tool` also reports `resources`: free physical RAM and how many CST
worker processes are alive. Each open 3D project holds about 700 MB, so check this
before a long job rather than after one fails.

### Step 1 — project

```
cst_connect_tool      {"launch_if_needed": true}
cst_new_project_tool  {"project_type": "mws"}      # saves into CST_MCP_WORKSPACE automatically
cst_open_project_tool {"path": "C:\\path\\to\\existing.cst"}
cst_save_project_tool {"path": "C:\\CST_MCP_workspace\\antenna.cst"}
cst_project_info_tool                              # confirm active_project + messages_tail
```

`cst_new_project_tool` saves immediately: a project left in CST's Temp folder is lost
when the session restarts, which is the usual cause of
`There is no active CST project currently.`

`cst_save_project_tool` needs `{"overwrite": true}` to target a path that already
exists — CST refuses otherwise and offers no overwrite flag of its own. When the target
is already the active project file the tool saves in place and deletes nothing.

### Step 2 — parameters

```
cst_get_parameters_tool                            # always read before writing
cst_define_parameters_tool {"parameters": {...}}   # create the parameter block
cst_set_parameters_tool    {"parameters": {...}}   # change a design point
cst_delete_parameter_tool  {"name": "temp_var"}
```

### Step 3 — model

Prefer the typed tools; each appends **one named history block** so the CST history tree
stays readable and the model stays parameterised.

```
cst_create_brick_tool               {component, name, xrange, yrange, zrange, material}
cst_create_cylinder_tool            {component, name, axis, radius, ranges, center, material}
cst_create_sphere_tool              {component, name, center, radius, material}
cst_create_cone_tool                {component, name, axis, bottom_radius, top_radius, ranges, material}
cst_create_torus_tool               {component, name, center, ring_radius, tube_radius, material}
cst_create_elliptical_cylinder_tool {component, name, axis, xradius, yradius, ranges, material}
cst_create_bondwire_tool            {name, point1, point2, height, radius, material, wire_type}
cst_boolean_tool                    {operation: add|subtract|intersect|insert, target, tool}
cst_transform_tool                  {operation: translate|rotate|scale|mirror, name, ...}
cst_extrude_curve_tool              {component, name, curve, thickness}
cst_new_component_tool              {name}
cst_move_solid_to_component_tool    {solid, component}
cst_rename_solid_tool               {old_name, new_name}
cst_delete_solid_tool               {name}
cst_add_to_history_tool             {title, vba_code}   # anything the typed tools do not cover
```

Coordinates accept **CST expressions**: `["-Lg/2", "Lg/2"]`, `["-h-tcond", "-h"]`.

`cst_transform_tool` refuses inputs the operation cannot honour rather than emitting a
silent no-op: `scale` without three factors and `mirror` without a plane both raise,
and `center` is rejected for `translate` (which moves by `vector` only).

### Step 4 — materials

```
cst_load_material_from_library_tool {"library_path": "FR-4 (lossy)", "material_name": "FR4_substrate"}
cst_create_material_tool            {"name": "MCP_FR4", "material_type": "Normal",
                                     "epsilon": 4.3, "tan_d": 0.025, "tan_d_freq": 2.45}
cst_assign_material_tool            {"solid": "board:substrate", "material": "MCP_FR4"}
```

A library material must exist in the project before a solid can reference it by name —
CST answers `The specified material does not exist` otherwise.

CST's loader always names the project material after the **library** entry, so
`material_name` is applied as an explicit `Material.Rename` afterwards. **Use the
returned `material` key**, not the library name, when assigning it to a solid. The tool
reports `library_material` and `renamed` so the two are never confused.

`library_path` accepts either separator (`FR-4 (lossy)` or `Substrates/FR-4 (lossy)`).

### Step 5 — ports

```
cst_add_discrete_port_tool  {"port_number": 1, "point1": [-30, 0, -1.6],
                             "point2": [-30, 0, 0.035], "impedance": 50.0}
cst_add_waveguide_port_tool {"port_number": 1, "orientation": "zmin",
                             "xrange": [-10, 10], "yrange": [-5, 5], "zrange": [0, 0]}
cst_list_ports_tool
```

| Situation | Port | Why |
| --- | --- | --- |
| Lumped feed, microstrip, matching network | **discrete** | the reference impedance is exactly what you set |
| Genuine waveguide aperture at the port plane | **waveguide** | modal, but check the cutoff afterwards |
| Thin microstrip cross-section | **not waveguide** | the mode can be evanescent across the whole band |

### Step 6 — solver and frequency

```
cst_set_solver_tool                  {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool         {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}
cst_configure_fd_solver_tool         {"mesh": "Tetrahedral", "sweep": "General Purpose",
                                      "order": "Second", "accuracy": "1e-4", "mesh_adaption": false}
cst_configure_td_solver_tool         {"accuracy": "-30", "mesh_type": "Hexahedral"}
cst_configure_eigenmode_solver_tool  {"n_modes": 3, "mesh_type": "Tetrahedral Mesh"}
cst_get_solver_tool
cst_frequency_overview_tool          # solver + band + monitors in one view
```

Valid solver strings include `HF Time Domain`, `HF Frequency Domain`, `HF Eigenmode`,
`HF IntegralEq`, `HF Multilayer`, `HF Asymptotic`, `LF EStatic`, `LF MStatic`,
`LF Stationary Current`, `LF Frequency Domain`, `LF Time Domain (MQS)`,
`Thermal Steady State`, `Thermal Transient`, `Mechanics`, `Cable Solver`.
Plain-English aliases (`frequency domain`, `time domain`, `eigenmode`) are accepted.

`cst_set_frequency_range_tool`'s `unit` is applied for real (`Units.SetUnit`), because
`Solver.FrequencyRange` interprets its numbers in the **project** unit. Allowed:
`Hz`, `kHz`, `MHz`, `GHz`, `THz`.

For the exact enum values each solver accepts, and the traps in them, read the
`cst2026-simulation-execution` skill rather than guessing.

### Step 7 — domain, mesh, monitors

```
cst_set_boundary_tool   {"all": "expanded open"}      # or per side
cst_set_symmetry_tool   {"y": "magnetic"}             # must match the real field symmetry
cst_set_background_tool {"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": true}
cst_set_mesh_tool       {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12}
cst_add_monitor_tool    {"name": "farfield_2400", "field_type": "Farfield", "frequency": 2.4}
cst_list_monitors_tool
```

**There is no separate meshing step.** CST 2026.2 exposes no VBA command that builds the
mesh on its own — the `Mesh` object carries settings only, and a bare `Mesh` statement
fails with `Default property usage is invalid`. The mesh is built by the solver, so go
straight to `cst_run_solver_tool`. `cst_generate_mesh_tool` exists only to explain this
and always raises.

**If the model has a small feature relative to the wavelength**, declare it so the solver
can factor the system:

```
cst_set_mesh_tool {"mesh_type": "Tetrahedral", "smallest_feature_mm": 2.0}
```

Without it, element size follows the wavelength alone: a 2 mm gap in a 0–100 MHz model
(3000 mm wavelength) is left unresolved and the solver stops with
`ERROR: Could not compute preconditioner.`

Monitor `field_type` aliases: `farfield`, `e`/`efield`, `h`/`hfield`, `powerflow`,
`current`, `powerloss`, `eenergy`, `henergy`. The `TimeMonitor` object uses a *different*
vocabulary (`"E-Field"`, `"B-Field"`); the server restricts you to the `Monitor`
vocabulary on purpose. Monitor indices are **0-based**.

### Step 8 — solve

```
cst_save_project_tool
cst_run_solver_tool        # on failure returns ok:false plus the CST error text
cst_messages_tool          {"limit": 20, "errors_only": true}
```

### Step 9 — verify

```
cst_list_results_tool
cst_read_result_tool                 {"tree_path": "1D Results\\S-Parameters\\S1,1"}
cst_read_s11_tool                    {"target_frequency": 2.4}
cst_read_reference_impedance_tool
cst_read_port_info_tool              {"operating_frequency": 2.4}
cst_energy_summary_tool              {"frequency": 2.4}
cst_model_audit_tool                 # solids, materials, volumes, bounding boxes
```

### Step 10 — evidence

```
cst_export_touchstone_tool  {"filename": "...\\evidence\\s11", "impedance": 50.0, "data_format": "RI"}
cst_export_ascii_tool       {"tree_path": "1D Results\\S-Parameters\\S1,1", "filename": "...\\s11.txt"}
cst_write_summary_json_tool {"out_path": "...\\evidence\\summary.json", "target_frequency": 2.4}
cst_save_project_tool
```

### Step 11 — release CST

```
cst_quit_tool
```

Call this when the job is done. It closes **every** open project and then closes the
Design Environment process itself. Each open 3D project keeps a ~700 MB
`modeler_AMD64.exe` alive, so leaving projects open is what eventually makes the next
solve fail with `Error during construction of pre-conditioner. Not enough memory.`
(`cst_close_project_tool` closes only the active project — not enough on its own.)

## Minimal working example

```text
cst_health_check_tool            {}
cst_connect_tool                 {"launch_if_needed": true}
cst_new_project_tool             {"project_type": "mws"}
cst_define_parameters_tool       {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6, "tcond": 0.035}}
cst_load_material_from_library_tool {"library_path": "FR-4 (lossy)", "material_name": "FR4"}
cst_create_brick_tool            {"component": "board", "name": "substrate",
                                  "xrange": ["-Lg/2", "Lg/2"], "yrange": ["-Wg/2", "Wg/2"],
                                  "zrange": ["-h", "0"], "material": "FR4"}
cst_create_brick_tool            {"component": "board", "name": "ground",
                                  "xrange": ["-Lg/2", "Lg/2"], "yrange": ["-Wg/2", "Wg/2"],
                                  "zrange": ["-h-tcond", "-h"], "material": "PEC"}
cst_add_discrete_port_tool       {"port_number": 1, "point1": ["-Lg/2", 0, "-h"],
                                  "point2": ["-Lg/2", 0, "tcond"], "impedance": 50.0}
cst_set_solver_tool              {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool     {"fmin": 2.0, "fmax": 3.0, "unit": "GHz"}
cst_configure_fd_solver_tool     {"mesh": "Tetrahedral", "order": "Second"}
cst_set_boundary_tool            {"all": "expanded open"}
cst_set_mesh_tool                {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12}
cst_save_project_tool            {"path": "C:\\CST_MCP_workspace\\demo.cst"}
cst_run_solver_tool              {}
cst_read_reference_impedance_tool {}
cst_read_s11_tool                {"target_frequency": 2.4}
cst_export_touchstone_tool       {"filename": "C:\\CST_MCP_workspace\\evidence\\s11"}
cst_quit_tool                    {}
```

## The runtime / toolbox family (16 tools)

These wrap a vendored command catalogue and workspace pipelines. They are **secondary**:
prefer the native tools above for live CST control, and reach for these when you need a
predefined multi-step command, a result-export helper, or an optimization pipeline.

They come as two interchangeable families with the same surface — `cst_runtime_*` and
`cst_toolbox_*` (8 implementations each, dual-named). Use whichever the environment
reports as available.

| Need | Tool |
| --- | --- |
| detect the runtime | `cst_runtime_detect_tool` / `cst_toolbox_detect_tool` |
| list available commands | `cst_runtime_list_tools_tool` / `cst_toolbox_list_tools_tool` |
| inspect a command's schema | `cst_runtime_describe_tool` / `cst_toolbox_describe_tool` |
| build an args JSON template | `cst_runtime_args_template_tool` / `cst_toolbox_args_template_tool` |
| invoke a command | `cst_runtime_invoke_tool` / `cst_toolbox_invoke_tool` |
| list pipelines | `cst_runtime_list_pipelines_tool` / `cst_toolbox_list_pipelines_tool` |
| usage guide | `cst_runtime_usage_guide_tool` / `cst_toolbox_usage_guide_tool` |
| inspect the schema catalogue | `cst_toolbox_schema_catalog_tool` |
| generate typed wrappers | `cst_toolbox_generate_typed_wrappers_tool` |

`cst_runtime_invoke_tool` takes a command name plus a JSON args object:

```json
{"tool_name": "list-result-items",
 "args": {"project_path": "C:\\CST_MCP_workspace\\case.cst"}}
```

Start with `cst_runtime_usage_guide_tool` — it documents the built-in commands. Do not
use typed-wrapper generation as part of a normal simulation workflow; it is a
development helper.

## Choosing between layers

1. **A native `cst_*` tool exists for the action** → use it.
2. **No native tool, but it is expressible as VBA** → `cst_add_to_history_tool` with a
   small, clearly titled block (see the rule about parameters), or `cst_run_vba_tool` for
   immediate execution that should not appear in the history tree.
3. **A runtime/toolbox command already does it** → use `cst_runtime_invoke_tool` rather
   than rebuilding it out of history blocks.
4. **Nothing covers it** → prefer extending the server (see
   `extending-and-conventions.md`) over one-off scripts.

Do not invent tool names. When unsure, list the live surface with
`cst_list_mcp_tools_tool`, or read `docs/mcp_tools.json`.

---

## Related documents

* [Workflow by operating mode](workflow.md) — the modes these steps serve
* [Guard rails and known limits](guard-rails-and-limits.md) — the traps each step avoids
* [Extending the server](extending-and-conventions.md) — what to do when no tool covers the action
* [Tool catalogue](../../../docs/use/tool-catalogue.md) — the same 84 tools described for users
* [Machine-readable tool manifest](../../../docs/mcp_tools.json) — the exact signature of every tool
