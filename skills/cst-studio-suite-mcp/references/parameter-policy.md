# Parameter policy: what to ask, what to default, what to derive

Use this when the user omits inputs or says to proceed with defaults.

## Ask once for critical inputs

Ask a single compact question, and only when the missing value would change the meaning
of the simulation. If several are missing, present the **defaults card** (below) rather
than asking a sequence of questions.

| Input | Why it matters |
| --- | --- |
| case type | a patch antenna, array, NFC coil, filter, cavity and waveguide need different setups |
| target frequency or band | drives dimensions, solver range, mesh and monitors |
| project source | decides new-model vs inspect-and-edit |
| execution intent | CST solves can be slow or licence-bound |
| primary objective | S11, gain, directivity, field strength, mode frequency, coupling or efficiency imply different outputs |

## Defaultable inputs

Use these when the user says "use defaults" / "先默认" / "directly run". **State every
defaulted value in the report.**

| Input | Default |
| --- | --- |
| units | `mm`, `GHz` (set with `Units.SetUnit` — the frequency unit decides how the band is read) |
| background | vacuum / air: `cst_set_background_tool {"epsilon": 1.0, "mue": 1.0}` |
| metal | Copper, from the CST material library |
| antenna boundary | `expanded open` |
| antenna solver | HF Time Domain for broadband sweeps; HF Frequency Domain for narrowband / high-Q accuracy |
| eigenmode solver | HF Eigenmode |
| frequency range | `0.7·f0` … `1.3·f0`; for 77 GHz radar use 76–81 GHz |
| mesh | `steps_per_wavelength` 10–12; add `smallest_feature_mm` whenever a gap or thickness is small against the wavelength |
| monitors | S-parameters plus far field at `f0`; add near-field or current only when useful |
| outputs | S11, VSWR, realized gain / gain / directivity, radiation pattern, result tree, Markdown report |
| run directory | `<CST_MCP_WORKSPACE>/cst_runs/<short_task>_<YYYYMMDD>/` |

## Derived inputs

For template-based new models, derive the first geometry from the frequency:

* **Free-space wavelength:** `lambda0_mm = 299.792458 / f_GHz`.
* **Patch dimensions:** use the microstrip patch relations in `templates.md`. Treat the
  result as a **starting point**, not an optimized design.
* **Substrate outline:** patch size plus margin, typically 3–6 substrate heights, or
  about 1.5–2.5× the patch dimensions.
* **Feed location:** template default first, then tune if S11 is poor.
* **Far-field monitor frequency:** centre frequency unless several are requested.
* **Mesh refinement:** ports, feed line / gap, patch edges, coil traces, thin dielectrics —
  or simply declare `smallest_feature_mm`.

## Existing-project inputs

When a `.cst` already exists, **inspect before asking for anything**. Read from the
available tools:

| What | How |
| --- | --- |
| project path, active project | `cst_project_info_tool` |
| parameters and values | `cst_get_parameters_tool` |
| geometry, entity names | `cst_model_audit_tool` |
| materials | `cst_model_audit_tool` (per-solid material) |
| ports | `cst_list_ports_tool` |
| solver, frequency range, monitors | `cst_frequency_overview_tool`, `cst_get_solver_tool` |
| result tree | `cst_list_results_tool` |
| recent messages / log | `cst_messages_tool` |

Ask only about genuinely ambiguous choices — which parameter to study, or which result
item is the objective.

## Defaults card

Present this shape before an expensive solve:

```text
I will run this CST setup unless you change it:

Case:
Project:
Frequency:
Material/substrate:
Solver:
Boundary:
Ports/excitation:
Monitors:
Outputs:
Run mode:
Working directory:
```

If the user already said "directly run" or "use defaults", continue and include the card
in the final report instead of pausing.

## What not to do

* Do not invent a value for the **case type** or the **objective** — those change what is
  built, not just how it is run.
* Do not silently pick a mesh level for a model with a sub-wavelength feature; declare
  `smallest_feature_mm` and say so.
* Do not default the **frequency unit** implicitly. `cst_set_frequency_range_tool` applies
  the unit you pass; a wrong unit is a 1000× wrong band.

---

## Related documents

* [Starting templates](templates.md) — where the derived dimensions are used
* [Workflow by operating mode](workflow.md) — the flows these inputs feed
* [Tool catalogue and call order](tool-catalogue-and-order.md) — the calls that apply each default
* [Guard rails and known limits](guard-rails-and-limits.md) — the limits behind the do-not rules
