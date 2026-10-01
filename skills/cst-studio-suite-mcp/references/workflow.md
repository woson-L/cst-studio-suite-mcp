# Workflow by operating mode

Task routing and execution order. Every mode ends with release and report.

## Universal preflight

1. Classify the request: plan only, new project, existing project edit, parameter study,
   or optimization (see the table in `SKILL.md`).
2. Check the MCP and CST with `cst_health_check_tool` then `cst_detect_tool`. The health
   report also gives free RAM and the live CST worker count — check it before a long job,
   not after one fails.
3. Connect with `cst_connect_tool`; pass `launch_if_needed: true` only when the user wants
   execution or live inspection.
4. Choose a run directory: `<CST_MCP_WORKSPACE>/cst_runs/<short_task>_<YYYYMMDD>/`, unless
   the user specified a path.
5. Record whether the task is destructive, expensive, or plan-only.

**Do not start CST for a plan-only task.** Return the workflow, the assumptions, the
expected outputs, and the tools that would be used.

A Design Environment that is reused from an earlier client session can answer parameter
commands with `A command is used in the wrong thread context`. If you hit that, run
`cst_quit_tool` and reconnect for a clean DE.

## New project flow

1. Select a template from `templates.md`, or derive a case-specific setup.
2. Resolve inputs with `parameter-policy.md`.
3. Show the defaults card if the solve may be expensive.
4. Create the project:

   ```
   cst_new_project_tool  {"project_type": "mws", "path": "<run_dir>/<name>.cst"}
   ```

   It saves immediately — a project left in CST's Temp folder is lost between calls,
   which is the usual cause of `There is no active CST project currently.`

5. Set units and background first, then build up in **small, named history blocks**:

   | Order | Content | Tools |
   | --- | --- | --- |
   | 1 | units and background | `cst_run_vba_tool` (`Units.SetUnit`), `cst_set_background_tool` |
   | 2 | materials | `cst_load_material_from_library_tool` / `cst_create_material_tool` |
   | 3 | geometry | `cst_create_*_tool`, `cst_boolean_tool`, `cst_transform_tool` |
   | 4 | ports / excitations | `cst_add_discrete_port_tool` / `cst_add_waveguide_port_tool` |
   | 5 | boundaries and symmetry | `cst_set_boundary_tool`, `cst_set_symmetry_tool` |
   | 6 | mesh | `cst_set_mesh_tool` |
   | 7 | solver and frequency range | `cst_set_solver_tool`, `cst_set_frequency_range_tool`, `cst_configure_*_solver_tool` |
   | 8 | monitors | `cst_add_monitor_tool` |

6. **Verify the model before solving**: `cst_model_audit_tool` (solids, materials,
   volumes, bounding boxes) and `cst_list_ports_tool`. A boolean that silently did nothing
   is much cheaper to catch here.
7. Save with `cst_save_project_tool`.
8. Solve with `cst_run_solver_tool`, then read `cst_messages_tool`.
9. List results with `cst_list_results_tool`; read 1D items with `cst_read_result_tool`;
   export with `cst_export_touchstone_tool` / `cst_export_ascii_tool`.
10. Validate against `result-validation.md`, then generate the report.
11. Release with `cst_quit_tool`.

## Existing project flow

1. Locate the source `.cst` file, or use the active project.
2. Inspect with `cst_project_info_tool`, and `cst_list_results_tool` when useful.
3. **Copy** the source `.cst` **and its companion folder** into the run directory before
   editing — CST results and metadata live beside the file, not inside it.
4. Open the working copy with `cst_open_project_tool`.
5. Read what is actually there before changing anything: parameters, solids, materials,
   ports, boundaries, solver, band, monitors, result tree.
6. Change **only** what was requested.
7. Save, solve, export, validate, report.
8. Release with `cst_quit_tool`.

Never rebuild an existing project from scratch unless the user asks for a rebuild.

## Parameter study flow

Two tools, deliberately split so the expensive half is never entered blind:

1. **Preview first — always.**
   ```
   cst_sweep_preview_tool {"parameters": {"L": "48:52:2"}, "mode": "single"}
   ```
   It never opens CST and never writes files, so it is free to call. It turns
   "sweep L and w" into a concrete case count.
   Value specs accept a list (`[48, 50]`) or a range string (`"48:52:2"`).
   `mode`: `single` (vary the first parameter only), `zip` (pair values, shortest wins),
   `cartesian` (full product — the only mode whose count multiplies).
   `max_cases` is a guard, not a target: exceeding it raises rather than running.

2. **Show the count, then run.**
   ```
   cst_sweep_run_tool {"project_path": "<source>.cst", "parameters": {"L": "48:52:2"},
                       "mode": "single", "run_solver": false}
   ```
   Each case gets its **own copy** of the source project — nothing is modified in place.
   `run_solver` defaults to `false`: a 100-case sweep with solves can take hours, so the
   cheap mode is the default and solving is an explicit decision.

3. Output defaults to `<source folder>/sweeps/<project>_<timestamp>/` and does not depend
   on `CST_MCP_WORKSPACE`. Report from `sweep_summary.csv` (per-case table) and
   `sweep_manifest.json` (full record) — never from memory.

4. Release with `cst_quit_tool`.

### Before you sweep, prove the project can rebuild

**A sweep changes parameters, and a parameter change rebuilds the model. If the project
cannot rebuild after being reopened, every case fails** — and the failure looks like a
sweep bug when it is not.

Measured on this build: a material brought in from the CST library
(`cst_load_material_from_library_tool`) does **not** persist into the saved `.cst`.
Reopening the project and rebuilding then stops at the solid that uses it:

```
(&H8000ffff) The specified material does not exist: Iron
(.Create)
```

So: confirm the project rebuilds after a save/reopen **before** starting a study, and
prefer materials defined in the project (`cst_create_material_tool`) for anything that
must be rebuilt in a later session. Also note the parameter value is written even when
the rebuild fails, so a clean `cst_set_parameters_tool` is not by itself proof the case
worked — read the value back **and** check the geometry moved.

### When you need something the sweep tools do not do

`cst_write_summary_json_tool` captures a per-case summary; `cst_list_results_tool` +
`cst_read_result_tool` extract a metric; the runtime wrappers
(`cst_runtime_invoke_tool`) expose a broader command catalogue. For anything further,
extend the server rather than hand-rolling a loop — see
`docs/extend/add-a-tool-family.md`.

## Optimization flow

1. Confirm the objective type, target, parameter bounds, maximum rounds, and stopping
   rule. **Without a stopping rule, do not loop.**
2. Inspect what the runtime offers before hand-rolling anything:
   `cst_runtime_list_pipelines_tool` (or `cst_toolbox_list_pipelines_tool`),
   `cst_runtime_describe_tool`, `cst_runtime_usage_guide_tool`.
3. Prefer the runtime helpers for multi-round loops. Do not hand-write a large optimizer
   unless the user explicitly asks for custom code.
4. Every round must contain: prepare parameters → run the simulation → export/read the
   result → compute the objective → decide stop/continue.
5. Stop early when the target is met or the configured no-improvement rule fires.
6. Record the full history (round, parameters, objective, decision) in the report.
7. Release with `cst_quit_tool`.

Do not continue optimizing after the target is reached unless the user asks for more
exploration.

## Default report shape

Produce Markdown unless the user asked for something else:

* task summary and mode
* **status** (`validated` / `needs_validation` / `partial` / `blocked` / `plan_only`)
* source project path and working project path
* run directory
* assumptions and defaults that were applied
* tool sequence actually used
* parameter table
* solver, frequency range and monitor setup
* result file paths and result-tree items
* validation summary (see `result-validation.md`)
* issues, warnings, and the recommended next change

Include exact paths for every artefact. Do not fabricate solver status, mesh counts,
convergence, S11, gain, or mode frequencies.

---

## Related documents

* [Parameter policy](parameter-policy.md) — the inputs to resolve before building
* [Starting templates](templates.md) — the starting points the new-project flow selects from
* [Result validation](result-validation.md) — the status and evidence the report ends with
* [Tool catalogue and call order](tool-catalogue-and-order.md) — the exact call for each step
* [Adding a tool family](../../../docs/extend/add-a-tool-family.md) — when the sweep tools do not cover the study
