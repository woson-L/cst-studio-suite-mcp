# Result validation and reporting status

Use this before claiming any CST simulation succeeded, and before writing the final
report. The physical checks that establish *trust* in a number live in
`cst2026-simulation-execution/references/solve-verify-evidence.md`; this file defines
what **evidence** and which **status** the report must carry.

## Evidence requirements

A run is validated only when at least one concrete evidence source exists:

* a saved working `.cst` project path
* result-tree entries from `cst_list_results_tool`
* an exported Touchstone / JSON / CSV / TXT / image file
* a readable 1D result from `cst_read_result_tool`
* a solver log showing completion

If the solver command returns success but none of these exist, report
`needs_validation` — **not** success. Do not fabricate solver status, mesh counts,
convergence, S11, gain or mode frequencies.

## S-parameters

* Confirm the result item or the Touchstone export exists.
* Complex data → dB via `20*log10(abs(S11))`. Never label a raw complex magnitude as dB.
* State the frequency unit and the interpolation method if you evaluate at a target
  frequency.
* For a pass/fail claim, state the threshold, e.g. `S11 <= -10 dB at 2.4 GHz`.
* Also report the reference impedance — a correct-looking curve with the wrong `ZRef` is
  meaningless (see the execution skill).

```text
S11 validation:
- target:
- best frequency:
- S11 at target:
- minimum S11 in band:
- reference impedance:
- evidence file:
- status: pass / fail / needs_validation
```

## VSWR

If VSWR is not exported directly, derive it from the reflection coefficient magnitude:

```text
VSWR = (1 + |Gamma|) / (1 - |Gamma|)
```

Do **not** compute VSWR from a dB value without converting back to magnitude.

## Far field

* Use `Realized Gain`, `Gain` or `Directivity`. **`Abs(E)` is not gain.**
* State frequency, port/excitation, quantity, unit and coordinate convention.
* Record whether the data is 3D, a theta cut, a phi cut, or polar/cartesian.

```text
Far-field validation:
- quantity:
- frequency:
- peak value:
- main direction:
- evidence file / result item:
- status:
```

## Near field and current

* Confirm the monitor existed before the solve, or that the result tree contains the item
  afterwards (`cst_add_monitor_tool` must run **before** `cst_run_solver_tool`).
* State the field quantity, frequency/time, plane/cut/volume, and unit.
* Do not infer far-field gain from a near-field magnitude.

## Eigenmode

* Confirm mode-frequency entries exist.
* Report requested modes and solved modes.
* Give mode frequencies with units.
* Note the boundary types (PEC / electric wall, magnetic wall, open, symmetry), because
  they determine the modes.

## Parameter studies

* Include the planned case count and the actual completed / failed counts.
* Include the parameter table and the objective metric.
* Identify a best case **only if** the objective was computed from validated results.
* Report the mode used (one-factor-at-a-time, paired, or full cartesian).

## Report status values

| Status | Meaning |
| --- | --- |
| `validated` | solver ran and the requested result evidence was found and parsed |
| `needs_validation` | project or solver ran, but the requested evidence is missing or incomplete |
| `partial` | some outputs validated, others failed or were not generated |
| `blocked` | a CST / MCP / licence / input / project problem prevented meaningful execution |
| `plan_only` | planning or script generation was requested; nothing was executed |

## Minimum final report

* working project path
* source project path, when applicable
* run directory
* status, from the table above
* assumptions and defaults applied
* MCP tools actually used
* solver, frequency range and result setup
* evidence files and result-tree entries
* validation summary
* issues, warnings and the recommended next action

---

## Related documents

* [Solve, verify, evidence](../../cst2026-simulation-execution/references/solve-verify-evidence.md) — the physical checks that establish trust in a number
* [Guard rails and known limits](guard-rails-and-limits.md) — the failures these rules catch
* [Workflow by operating mode](workflow.md) — the report shape that carries the status
* [Rules that keep results trustworthy](../../../docs/use/rules.md) — the same rules stated for users
