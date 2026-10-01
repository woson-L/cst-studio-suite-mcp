# Starting templates

Templates are **starting points, not validated designs**. Simulate and validate before
making any performance claim, and say in the report that the geometry was a starting
point.

| Template | Use when | Status |
| --- | --- | --- |
| 2.4 GHz microstrip patch | stable first antenna case | primary |
| Rectangular PEC cavity, eigenmode | fast end-to-end smoke test of the MCP itself | validation case |
| 77 GHz 1×4 patch array | mmWave / ADAS showcase | only after the single patch is stable |
| Existing `.cst` rerun | user supplies a project, or wants the open model modified | primary |

## 2.4 GHz microstrip patch

| Field | Default |
| --- | --- |
| centre frequency | 2.4 GHz |
| sweep range | 2.0–3.0 GHz (or 1.8–3.0 GHz for a wider look) |
| substrate | FR-4 (`FR-4 (lossy)`) if loss accuracy is unimportant; a Rogers laminate if it matters |
| substrate thickness | 1.6 mm for FR-4 |
| metal | Copper for the patch, PEC acceptable for a quick run |
| feed | discrete port; or a microstrip line with the port at the board edge |
| boundary | `expanded open` |
| solver | HF Time Domain for a broad sweep; HF Frequency Domain for a narrow band |
| monitors | far field at 2.4 GHz |
| outputs | S11, VSWR, realized gain / directivity, radiation pattern |

Dimension guidance:

* Take λ/2 in the effective medium as the first patch length, then expect to tune it.
* Substrate and ground outline: patch plus margin (roughly 1.5–2.5× the patch, or 3–6
  substrate heights).
* Feed inset / position is a **tunable parameter**, not a derived constant.
* If the first S11 is poor, run a small parameter study over patch length and feed
  position (see `workflow.md` — there is no sweep tool, the loop is yours).

A worked call sequence for exactly this case, with measured numbers, is in
`cst2026-simulation-execution/references/worked-example.md`.

## Rectangular PEC cavity, eigenmode

The cheapest way to prove the MCP works end to end without a port.

| Field | Default |
| --- | --- |
| cavity | 100 × 50 × 30 mm brick |
| interior | vacuum / air |
| boundaries | `electric` on all six sides |
| solver | HF Eigenmode |
| modes | 3 |
| outputs | mode frequencies, result-tree evidence |

Set the solver first, then the modes:

```
cst_set_solver_tool                 {"solver": "HF Eigenmode"}
cst_configure_eigenmode_solver_tool {"n_modes": 3, "mesh_type": "Tetrahedral Mesh",
                                     "method": "Automatic"}
```

The **band is still the global solver frequency range**, so
`cst_set_frequency_range_tool` is required for an eigenmode job too — it is what the
solver searches in. `JDM` and `JDM (low memory)` are refused by CST 2026.2
(`Invalid Eigenmode solver type`); see `cst2026-simulation-execution/references/solver-and-band.md`.

## 77 GHz 1×4 patch array

Only attempt this once the single patch works — mmWave arrays are far more sensitive to
meshing, material loss, feed implementation and port definition.

| Field | Default |
| --- | --- |
| band | 76–81 GHz, centre 77 GHz |
| array | 1×4 linear patch array |
| substrate | RO3003 or similar low-loss mmWave laminate |
| substrate thickness | 0.127 mm if unspecified |
| element spacing | about 0.5 λ0, adjusted for layout |
| feed | corporate feed, or individual ports if coupling is the objective |
| solver | HF Frequency Domain or HF Time Domain depending on the requested outputs |
| monitors | far field at 77 GHz; optional 76 / 79 / 81 GHz |
| outputs | S11, mutual coupling if multiport, realized gain / directivity, main-beam direction |

At 77 GHz the wavelength is ~3.9 mm, so a 0.127 mm laminate is already a
sub-wavelength feature — declare it with `smallest_feature_mm` rather than relying on
`steps_per_wavelength` alone.

## Existing-project rerun

1. Copy the source `.cst` **and its companion folder** into the run directory.
2. Inspect parameters, solids, materials, ports, solver, band, monitors, result tree.
3. Apply only the requested parameter changes.
4. Save, solve, export.
5. Report before/after values with the evidence paths.

If the user does not say which parameter to change, list the candidate design parameters
and ask **once**.

## Template report requirements

Every template run must report:

* template name
* all assumed default values
* generated / working project path
* solver, frequency range or mode count
* ports / excitation
* monitors
* outputs and validation status (`validated` / `needs_validation` / …)

---

## Related documents

* [Workflow by operating mode](workflow.md) — the new-project flow that uses a template
* [Parameter policy](parameter-policy.md) — defaults and the derived-geometry formulas
* [Worked example](../../cst2026-simulation-execution/references/worked-example.md) — the 2.4 GHz patch run end to end, with measured numbers
* [Solver selection and band](../../cst2026-simulation-execution/references/solver-and-band.md) — the solver and eigenmode enums these templates set
