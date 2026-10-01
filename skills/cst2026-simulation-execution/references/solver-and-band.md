# Solver selection, band and solver configuration

Verified against CST Studio Suite 2026.2 (`_cst_results` 2026.2 Release from
2025-11-28). Where a documented CST command does **not** exist in this build, that is
stated with the error text it produces — those spellings waste the most time.

## Choosing the solver

```
cst_set_solver_tool {"solver": "HF Frequency Domain"}
cst_get_solver_tool {}
```

Valid strings (from CST's own `ChangeSolverType`):

```
HF Time Domain     HF Frequency Domain   HF Eigenmode      HF IntegralEq
HF Multilayer      HF Asymptotic         LF EStatic        LF MStatic
LF Stationary Current   LF Frequency Domain   LF Time Domain (MQS)
Thermal Steady State    Thermal Transient     Mechanics     Cable Solver
```

Plain-English aliases are accepted (`frequency domain`, `time domain`,
`eigenmode`). The tool reads the solver back from CST, so the reply shows what is
really active — trust that, not the request.

| Situation | Solver | Why |
| --- | --- | --- |
| Narrowband antenna, S-parameters, high-Q | **HF Frequency Domain** | direct solve at the band of interest |
| Broadband structure, many resonances | HF Time Domain | one run covers the whole band |
| Cavity / filter modes, no port | HF Eigenmode | returns mode frequencies |
| Open radiator, large electrical size | HF IntegralEq / HF Multilayer | free-space Green's function, no air box |
| Quasi-static device | LF EStatic / MStatic / Stationary Current | fields are not wave-like |

## The three different "frequency ranges"

Keep them separate or the report will be wrong:

| Name | Set with | Meaning |
| --- | --- | --- |
| `solver_frequency_range` | `cst_set_frequency_range_tool` | the band actually solved |
| `export_grid` | CST sweep default (1001 points) | where the curve is sampled |
| `field_monitor_frequencies` | `cst_add_monitor_tool` | discrete frequencies where fields/far field are stored |

Read all three at once:

```
cst_frequency_overview_tool {}
```

A monitor frequency outside the solver range is simply never computed. Set the
solver range to cover every monitor frequency plus margin.

```
cst_set_frequency_range_tool {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}
```

`unit` is applied for real: the tool issues `Units.SetUnit ("Frequency", ...)` and
reports the unit CST actually holds. `Solver.FrequencyRange` takes plain numbers
interpreted in the **project** unit, so without this a request for `MHz` in a GHz
project would set a 1000x wrong band. Allowed units: `Hz`, `kHz`, `MHz`, `GHz`,
`THz`; anything else is refused.

## Frequency domain

```
cst_configure_fd_solver_tool {"mesh": "Tetrahedral", "sweep": "General Purpose",
                              "order": "Second", "accuracy": "1e-4",
                              "mesh_adaption": false, "double_precision": true}
```

* `mesh`: `Hexahedral` | `Tetrahedral` | `Surface`
* `sweep`: `General Purpose` | `Fast reduced order model` | `Discrete samples only`
* `order` (tetrahedral): **`First` | `Second` | `Third`**, or `Mixed` for variable
  order. There is **no** `OrderTet` value `Mixed` — the tool maps `Mixed` to the
  separate `MixedOrderTet "True"` flag, which is what the old code got wrong.
* `accuracy` (tetrahedral): a tetrahedral relative residual, e.g. `1e-4`.
* `accuracy` (hexahedral/Surface): `FDSolver.AccuracyHex` takes a **relative residual
  norm in 1e-3 … 1e-12**, not a word. The words `Low`/`Medium`/`High`/`Very high` are
  accepted as aliases and mapped to `1e-3`/`1e-4`/`1e-5`/`1e-6`; a numeric value is
  range-checked. Previously a numeric value emitted **no accuracy line at all** while
  still reporting success.
* `mesh_adaption` is tetrahedral only (`FDSolver.MeshAdaptionTet`); requesting it for
  another mesh raises instead of being silently ignored.
* Parameters that cannot apply to the chosen mesh are listed in `not_applied`.

Tetrahedral is the better default for a thin substrate with curved or slanted
features; hexahedral is faster when the geometry is axis-aligned boxes.

## Time domain

```
cst_configure_td_solver_tool {"accuracy": "-30", "mesh_type": "Tetrahedral",
                              "stimulation_port": "All"}
```

* `accuracy` is the steady-state limit in dB, in `[-80, 0]`. `-30` is the CST
  default; `-40` for a cleaner late-time response at higher cost.
* The **Solver object has no `MeshType` and no `Reset`** in 2026.2
  (`(10091) ActiveX Automation: no such property or method`). The mesh comes from
  the Mesh object — call `cst_set_mesh_tool` too. The reply says so explicitly via
  `mesh_set_separately` / `mesh_setting_hint`.

## Eigenmode

```
cst_set_solver_tool                  {"solver": "HF Eigenmode"}
cst_configure_eigenmode_solver_tool  {"n_modes": 3, "mesh_type": "Tetrahedral Mesh",
                                      "method": "Automatic", "frequency": 2.4}
```

The 2026 reference defines `SetMethodType (method, mesh)` with a **per-mesh split**:

| Mesh | Valid methods | Mesh argument |
| --- | --- | --- |
| `Tetrahedral Mesh` | `Automatic`, `Classical (Lossless)`, `General (Lossy)` | `"Tet"` |
| `Hexahedral Mesh` | `Automatic`, `AKS` | `"Hex"` |

`AKS` and `JDM` are **hexahedral** methods. Pairing `AKS` with the tetrahedral mesh
was the original defect — the mesh argument follows the method, not the reverse.

**`JDM` and `JDM (low memory)` stay rejected even for the hexahedral mesh.** They are
documented CST values, but a live run on 2026.2 answers
`Invalid Eigenmode solver type: JDM` (see `tests/verify_live.py`, step
`eigenmode_reject_jdm`). Re-probe before enabling them on a newer build.

* `frequency` sets the solver's target frequency. The **band** is still the global
  solver frequency range, so `cst_set_frequency_range_tool` is required for an
  eigenmode job too.

## Failure modes specific to this layer

| Error | Cause |
| --- | --- |
| `Solver run failed. Frequency range not set correctly.` | range never set, or set after the solve configuration |
| `Invalid Eigenmode solver type: JDM` | JDM is refused by this build |
| `(10091) ActiveX Automation: no such property or method` | `Solver.MeshType` / `Solver.Reset` do not exist in 2026.2 |

---

## Related documents

* [Ports, boundaries and mesh](ports-boundaries-mesh.md) — the mesh settings the solver depends on
* [Solve, verify, evidence](solve-verify-evidence.md) — the verification set to run after the solve
* [Worked example](worked-example.md) — these settings in a runnable sequence
* [Tool catalogue and call order](../../cst-studio-suite-mcp/references/tool-catalogue-and-order.md) — the step order these calls sit in
* [What CST 2026.2 does not expose](../../../docs/use/cst-2026-limits.md) — the documented commands this build refuses
