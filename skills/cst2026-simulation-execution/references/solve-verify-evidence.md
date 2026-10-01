# Solve, verification, evidence and diagnosis

## Solve

```
cst_save_project_tool {}
cst_run_solver_tool   {}
cst_messages_tool     {"limit": 20, "errors_only": true}
```

`cst_run_solver_tool` returns `ok: false` **with the CST message text** when the solve
fails, and attaches a `memory` block. Read `messages_tail`; do not retry blind.

It also refuses to start when free physical RAM is below ~2 GB, because a
frequency-domain solve otherwise dies inside CST with
`Error during construction of pre-conditioner. Not enough memory.` Each open 3D project
holds roughly 700 MB in its own `modeler_AMD64.exe` worker, so call `cst_quit_tool`
between jobs. Pass `allow_low_memory: true` to override the guard.

**Important:** CST's message window is **cumulative across calls**. A stale `ERROR:`
from an earlier failed operation will be read back by a later operation. Before
concluding that a solve failed, check whether the result tree actually contains what
you expect (`cst_list_results_tool`).

## What counts as "simulated"

A solver that exits successfully is not a simulation. Four things must be true before
a result may be quoted:

| # | Requirement | How to check |
| --- | --- | --- |
| 1 | The solver **converged** | `cst_messages_tool` shows `... convergence criteria have been satisfied` and no `ERROR:` line |
| 2 | The **port mode propagates** in the band | `cst_read_port_info_tool`: cutoff frequency well below `fmin` |
| 3 | The **reference impedance** is what you intended | `cst_read_reference_impedance_tool`: discrete 50 Ω port must read `50+0j` |
| 4 | The **geometry is the one you think** | `cst_model_audit_tool`: expected solids, materials, volumes |

If any of the four is missing, the correct status for the job is `needs_validation`,
not "done".

## Verification set — run all of it, then report

```
cst_list_results_tool
cst_read_s11_tool                    {"target_frequency": 2.4}
cst_read_reference_impedance_tool
cst_read_port_info_tool              {"operating_frequency": 2.4}
cst_energy_summary_tool              {"frequency": 2.4}
cst_model_audit_tool
```

Quote the `verdict` from `cst_read_port_info_tool` verbatim. `OK` means the mode
propagates with the stated margin; `WARNING` means the cutoff is not below your lowest
operating frequency; `UNKNOWN` means the tool had no band to compare against and you
still owe that check.

### Number handling

* complex S-parameters → `S11_dB = 20*log10(abs(S11))` (never treat the real part as dB)
* linear efficiency → `eff_dB = 10*log10(eta)`
* VSWR from `|Γ|`, not from dB
* gain only from `Realized Gain`, `Gain` or `Directivity` — **`Abs(E)` is not gain**
* state the frequency unit and the interpolation method used to reach a target frequency

### Sanity checks worth doing every time

* **Efficiency:** FR-4 (`tanδ 0.025`) costs roughly 40–60 % of the input power. Total
  efficiency near 100 % on a lossy laminate means the loss model is wrong — often the
  substrate was assigned a loss-free material.
* **A flat S11 curve** away from any resonance usually means the port is not radiating
  into the structure, not that the antenna is broadband.
* **`power_accepted / power_stimulated` near 1 with a bad S11** is contradictory —
  read the reference impedance again.

## Evidence and reproducibility

```
cst_export_touchstone_tool  {"filename": "...\\evidence\\s11", "impedance": 50.0,
                             "data_format": "RI"}
cst_export_ascii_tool       {"tree_path": "1D Results\\S-Parameters\\S1,1",
                             "filename": "...\\evidence\\s11.txt"}
cst_write_summary_json_tool {"out_path": "...\\evidence\\summary.json",
                             "target_frequency": 2.4}
cst_save_project_tool       {"path": "...\\working.cst"}
```

* Touchstone `filename` is a **base name without extension** — CST appends
  `.s1p` / `.s2p`.
* ASCII export of a **1D** result is driven entirely by the tree selection:
  `SelectTreeItem` then `Execute`. CST 2026.2 has no `ASCIIExport.SetSubset`, and
  `Mode`/`Step` apply to 2D/3D field results only — passing `mode` for a 1D item is
  ignored and the reply says so.
* `cst_export_touchstone_tool` needs a **solved** project; otherwise CST reports
  `TOUCHSTONE export calculation failed.`
* Quote numbers from the exported files, not from a screenshot.
* Saving over an existing path needs `{"overwrite": true}`: CST refuses outright with
  `Failed to save project. The given path already exists` and has no overwrite flag.
  If the target is already the active project file the tool saves in place and never
  deletes anything.

## Diagnosis table

| Symptom | Most likely cause | Action |
| --- | --- | --- |
| `Frequency range not set correctly` | range never set, or set after the solve config | set solver → range → configure → save → solve |
| `Terminated on unknown error` | real cause is in the message window | `cst_messages_tool {"errors_only": true}` |
| `Error during construction of pre-conditioner. Not enough memory.` | genuine RAM shortage: orphaned CST workers, or a degenerate mesh ratio | `cst_quit_tool`; check the `memory` block; remove out-of-scale geometry |
| `Could not compute preconditioner.` (**no** memory wording) | a small feature is unresolved: element size follows the wavelength only | `cst_set_mesh_tool {"smallest_feature_mm": <smallest gap>}`; also check the domain is not needlessly large |
| `Default property usage is invalid. (Mesh)` | something emitted a bare `Mesh` statement | do not call `cst_generate_mesh_tool`; the solver meshes |
| `A command is used in the wrong thread context` | parameter VBA run against a Design Environment reused from another client session | `cst_quit_tool` first, then `cst_connect_tool` for a fresh DE |
| `Expecting an already dimensioned array. (u = GetUnit(...))` | bare `GetUnit` does not exist; the getter must be qualified | use `Units.GetUnit ("Frequency")` |
| `No excitation has been selected` | port edit failed, or no port exists | `cst_list_ports_tool`; rebuild the project if the port list is inconsistent |
| `The history list is not positioned at the very last entry` | a history block failed earlier | close and reopen the project; do not keep editing the broken tree |
| `There is no active CST project currently.` | new project left in CST's Temp folder | `cst_new_project_tool` (auto-saves into the workspace), or save immediately after creating |
| `TOUCHSTONE export calculation failed` | not solved, or wrong tree path | solve first; confirm `S1,1` exists with `cst_list_results_tool` |
| `The specified material does not exist` | a library material was referenced before being loaded into the project | `cst_load_material_from_library_tool` first; CST rejects the solid otherwise |
| S11 flat, no resonance | port not coupling, or mode evanescent | `cst_read_port_info_tool`, then re-place the port |
| Result identical after a geometry change | parameter change did not rebuild | `cst_get_parameters_tool` to confirm the value, then rebuild/re-solve |

---

## Related documents

* [Result validation](../../cst-studio-suite-mcp/references/result-validation.md) — the evidence and status values the report must carry
* [Ports, boundaries and mesh](ports-boundaries-mesh.md) — why the cutoff and ZRef checks matter
* [Solver selection and band](solver-and-band.md) — the band and solver failures in the diagnosis table
* [Worked example](worked-example.md) — reported numbers from a measured task
* [Verification](../../../docs/dev/verification.md) — the committed evidence behind these claims
