# Guard rails and known limits

## Rule 1 — parameters are changed only through `cst_set_parameters_tool`

Never put `StoreParameter`, `StoreParameters`, `StoreDoubleParameter` or `Rebuild`
inside `cst_add_to_history_tool`.

* CST 2026 answers a parameter change inside a history rebuild with
  `Prevented attempt to change the value for parameter X inside history rebuild`, and a
  `Rebuild` inside a structure macro with
  `(&H8000FFFF) The rebuild operation cannot be used inside a structure macro.`
* In testing, submitting that block through `cst_add_to_history_tool` left the Design
  Environment **permanently unresponsive** — every later call hung.
* The server therefore **refuses** such a block up front (`cst_add_to_history_tool`
  returns an error naming the offending token). This is deliberate: a clear rejection
  beats a hung CST session.

Working mechanism (verified on CST 2026.2):

```
cst_set_parameters_tool {"parameters": {"Lpatch": 26.91, "dinset": 21.6}}
```

Internally the server runs `StoreParameters` + `Rebuild` as a **`Sub Main` block** via
`Model3D._execute_vba_code`. That path is accepted; the history-tree path is not.

Parameter **names** are validated as plain identifiers (letters, digits, underscores,
dots). This is not cosmetic: the name is interpolated into the `StoreParameters` array,
so a name containing a quote is a VBA injection point.

## Rule 2 — save before solving, and set the frequency range first

A solver run without a frequency range fails with
`Solver run failed. Frequency range not set correctly.` Always:

```
cst_set_solver_tool            -> choose the solver
cst_set_frequency_range_tool   -> set the band
cst_save_project_tool          -> persist
cst_run_solver_tool            -> solve
```

## Rule 2b — saving back onto the same path needs `overwrite`

An iterative run saves the working copy onto its own path every round, and CST refuses
that unless the overwrite is explicit:

```
cst_save_project_tool  {"path": "<working copy>.cst", "overwrite": true}
```

`overwrite: true` closes whatever project still occupies that path and then lets CST
replace the `.cst` together with its companion `Result/` directory — no confirmation is
raised. Do **not** delete project files yourself to make room: removing only the `.cst`
leaves the companion directory in place and CST answers with `The project directory ...
already exists and is non-empty. It would be overwritten.`

## Rule 3 — a successful solve is not proof of a correct result

After every solve, verify the port before believing any S-parameter:

```
cst_read_reference_impedance_tool   # must equal the impedance you intended
cst_read_port_info_tool             # cutoff frequency must be below your band
```

Real failure this catches: a waveguide port on a 1.6 mm microstrip cross-section had a
**51.9 GHz cutoff** and a **6.2 kΩ** wave impedance at 2.4 GHz — the mode was
evanescent, the S-parameters were referenced to **7623 Ω instead of 50 Ω**, and S11
looked like a flat −0.6 dB line that is easy to mistake for an antenna. The solver had
reported success.

## Rule 4 — report numbers from files, not from the screen

Convert complex S-parameters yourself: `S11_dB = 20*log10(abs(S11))`.
Never present `Abs(E)` as gain — use `Realized Gain`, `Gain` or `Directivity`.
Export before quoting: `cst_export_touchstone_tool`, `cst_export_ascii_tool`,
`cst_write_summary_json_tool`.

## Rule 5 — release CST when the job ends

`cst_quit_tool` closes every project and the Design Environment. Each open 3D project
holds ~700 MB in its own `modeler_AMD64.exe`. Leaking them is what eventually produces
`Error during construction of pre-conditioner. Not enough memory.`
`cst_run_solver_tool` refuses to start when free RAM is below ~2 GB; pass
`allow_low_memory: true` to override.

## Pitfalls the tools already handle

| Pitfall | Handled by |
| --- | --- |
| Parameter change inside a history block breaks/blocks CST | `cst_set_parameters_tool`, plus a lint that rejects such blocks |
| VBA injection through a parameter **name** | identifier validation on the name, not just the value |
| New project lost in a Temp folder between calls | `cst_new_project_tool` saves into `CST_MCP_WORKSPACE` |
| Solver failure reported as `Terminated on unknown error` | `cst_run_solver_tool` appends the CST message window |
| Wrong method names (`MaterialUnit`, `Color`, `LoadFromLibrary`, `Monitor.GetName`, `ResetBackground`, `Mue`) | replaced with the spellings verified against CST 2026.2 |
| Monitor indices treated as 1-based | 0-based, verified |
| `MaterialUnit "GHz","mm"` → `Invalid unit dimension type` | replaced with `FrqType "hf"` + `Colour` |
| Cone with both radii zero | rejected before CST sees it |
| `SetSubset` / `Mode` on a 1D ASCII export | removed; 1D export is selection-driven |
| Saving onto an existing project path, including one that is still open | `{"overwrite": true}` — CST's own `allow_overwrite`, plus closing the project that holds that path; this server never deletes project files |
| `Invalid Eigenmode solver type` values, invalid `OrderTet "Mixed"`, invalid boundary kind `none` | the allow-lists now match CST's documented enums |
| A numeric hexahedral accuracy that was silently dropped | range-checked and emitted; words map to numbers |
| Freeing orphaned CST workers | `cst_quit_tool` closes all projects and releases the DE |

## Known limits

* **A library-loaded material does not survive save/reopen.** Measured: after
  `MaterialLibrary.LoadMaterialFromLibrary ("Iron", "", True)` and a save, reopening the
  project and rebuilding fails at the solid that uses it —
  `(&H8000ffff) The specified material does not exist: Iron (.Create)`. Because changing
  a parameter necessarily rebuilds, **a parameter sweep over a project using library
  materials fails on every case**. Prefer materials defined in the project
  (`cst_create_material_tool`) for any model that must be rebuilt in a later session, and
  before sweeping a project, first confirm it can still rebuild *after being reopened*.
  Note the parameter value itself is written even when the rebuild fails, so a successful
  `StoreParameters` is **not** evidence that the case worked — read the value back **and**
  confirm the geometry moved.
* **No standalone mesh generation.** CST 2026.2 has no such VBA command; the solver
  meshes. `cst_generate_mesh_tool` always raises and only documents this.
* **`GetUnit` must be qualified**: `Units.GetUnit ("Frequency")`. A bare `GetUnit`
  fails with `Expecting an already dimensioned array`.
* **`JDM` eigenmode method** is a documented CST value but is refused by this build
  (`Invalid Eigenmode solver type: JDM`). Re-probe before enabling it.
* A parameter value containing a comma is rejected as a likely list — CST expects one
  expression per parameter.
* `capture-3d-view` style PNG export is not exposed; use CST's own image export.
* Remote/MPI/distributed solving is not exposed.
* The CST message window is **cumulative across calls**: a stale `ERROR:` from an
  earlier failed operation is read back by later ones. Error detection matches on the
  message **type** only, but old messages still appear in `messages_tail` — check
  `cst_list_results_tool` before concluding a solve failed.
* `cst_energy_summary_tool` omits a key it could not read rather than failing; a missing
  efficiency is "not measured", not zero.

---

## Related documents

* [Tool catalogue and call order](tool-catalogue-and-order.md) — where each guarded call sits in the sequence
* [Result validation](result-validation.md) — how a verified result must be reported
* [Parameter policy](parameter-policy.md) — the input rules Rule 1 depends on
* [What CST 2026.2 does not expose](../../../docs/use/cst-2026-limits.md) — check before filing a bug
* [Known limits of the server](../../../docs/use/known-limits.md) — the server-side limits
