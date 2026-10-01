# Ports, boundaries, background and mesh

## Ports

A port is where most meaningless S-parameters come from. Read this before reporting
any S-parameter.

```
cst_add_discrete_port_tool  {"port_number": 1,
                             "point1": [-30, 0, -1.6], "point2": [-30, 0, 0.035],
                             "impedance": 50.0}
cst_add_waveguide_port_tool {"port_number": 1, "orientation": "zmin",
                             "xrange": [-10, 10], "yrange": [-5, 5], "zrange": [0, 0],
                             "n_modes": 1}
cst_list_ports_tool {}
```

* **Discrete port** — two points across the feed gap; the S-parameters are referenced
  to exactly the impedance given. The safe default for microstrip, lumped feeds and
  any matching network. Place it at the **physical feed plane**: for an inset-fed
  patch that is where the line meets the patch, for a stub feed that is the board
  edge.
* **Waveguide port** — `orientation` is the feeding direction (`zmin` means the port
  sits at the lower z boundary, feeding +z; valid: `xmin`, `xmax`, `ymin`, `ymax`,
  `zmin`, `zmax`). Only use it where a genuine waveguide mode exists at the port
  plane, and always run `cst_read_port_info_tool` afterwards.
* A `DiscreteFacePort` cannot be driven from coordinates — CST answers
  `only picked coordinates are allowed for face ports`. Use `DiscretePort`.
* Deleting ports: `Port.Delete n` removes a **waveguide** port. When a port has to
  change type, the reliable route is a clean rebuild of the project, because a failed
  port edit can leave the model in a state where the solver refuses to start
  (`No excitation has been selected`).

### The two port defects that produce believable wrong results

**1. Evanescent port mode.** A waveguide port on a thin microstrip cross-section: the
solver succeeds, the result tree contains `S1,1`, and S11 looks like a smooth curve.
Observed on a 1.6 mm FR-4 microstrip at 2.4 GHz:

| Result tree item | Value |
| --- | --- |
| `1D Results\Port Information\Cutoff Frequency\1(1)` | **51.95 GHz** |
| `1D Results\Port Information\Wave Impedance\1(1)` | 6207 Ω |
| `1D Results\Reference Impedance\ZRef 1(1)` | **7623 Ω** (not 50) |
| `1D Results\S-Parameters\S1,1` | flat ≈ −0.6 dB |

A cutoff above the band means the mode is evanescent and every S-parameter is
meaningless. For a microstrip or lumped feed use `cst_add_discrete_port_tool`.

**2. Wrong reference impedance, right-looking curve.** `ZRef` is normalised to
whatever the port mode defines, not to what the user means by "50 Ω". Read
`cst_read_reference_impedance_tool` for every solved project before reporting.

`cst_read_port_info_tool` returns a `verdict` that already applies the cutoff rule.
Pass `operating_frequency` to state the band you care about; without it the tool reads
the project's own lower band edge from the solver (`Solver.GetFmin`), and if that read
fails it returns `UNKNOWN` rather than a misleading `OK`. Treat `UNKNOWN` as a task,
not a pass.

## Boundaries, symmetry, background

```
cst_set_boundary_tool   {"all": "expanded open"}
cst_set_symmetry_tool   {"y": "magnetic"}
cst_set_background_tool {"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": true}
```

* Boundary kinds: `expanded open`, `open`, `open (add space)`, `electric`,
  `magnetic`, `tangential`, `normal`, `periodic`, `unit cell`, `conducting wall`.
  Radiating structures use `expanded open`. The per-face arguments (`xmin` … `zmax`)
  default to `expanded open`, so `{"all": "..."}` is a convenience for setting all six.
* `none` is **not** a boundary type — it exists only for
  `Xsymmetry`/`PotentialType`/`TemperatureType`, so accepting it here sent CST an
  invalid value. Values are matched case-insensitively and the canonical lower-case
  spelling is what reaches CST.
* CST's background default is **PEC**, not vacuum — always set `epsilon 1.0`
  explicitly for an open, radiating problem.
* Symmetry halves the solve time but must match the true field symmetry. A wrong
  symmetry plane gives a confident wrong answer, so enable it only when the geometry
  *and* the excitation are symmetric about that plane.
* Periodic/unit-cell phase shifts are honoured by the frequency domain and eigenmode
  solvers; the transient solver ignores them.
* The `Background` object uses **`Reset`** and **`Mu`**. The macro-recorder names
  `ResetBackground` / `Mue` appear nowhere in the 2026 reference; they happened to be
  accepted by this build, but the documented spelling is what the tool now emits.

## Mesh

```
cst_set_mesh_tool {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12}
cst_set_mesh_tool {"mesh_type": "Tetrahedral", "smallest_feature_mm": 2.0}
```

**There is no meshing call to make.** CST 2026.2 exposes no VBA command that builds
the mesh on its own: the `Mesh` object documented in the VBA reference carries
settings only (`MeshType`, `StepsPerWavelengthTet`, `MinimumStepNumberTet`,
`DelaunayOptimizationLevel`, …). Verified absent or failing — 17 spellings tested:

```
Mesh                  -> Default property usage is invalid
Mesh.Create           -> Method or property not found
Mesh.Reset            -> Method or property not found
Mesh.CreateMesh / Mesh.StartMeshing / Mesh.GenerateMesh / Mesh.AdaptiveMeshing
Mesh.SetMeshType / Mesh.Name / MeshGeneration / Call Mesh / x = Mesh
Model3D.Mesh / MeshAdaption3D.Reset / MeshAdaption3D.Create / MeshAdaption3D.Start
MeshShapes.Create     -> all fail
```

The mesh is built by the solver, so go straight to `cst_run_solver_tool`.
`cst_generate_mesh_tool` is retained only to explain this and always raises.

* `mesh_type`: `HexahedralFIT` | `HexahedralTLM` | `Tetrahedral` | `Surface` |
  `SurfaceML` | `Planar`
* `steps_per_wavelength` (tetrahedral): max edge length as a fraction of a
  wavelength. **10–12** is a reasonable default.
* `lines_per_wavelength` (hexahedral FIT): `20` is typical for antenna work.
* `min_step_number`: overrides `smallest_feature_mm` when both are given.
* `smallest_feature_mm`: give the model's smallest gap or thickness and the required
  `MinimumStepNumberTet` is derived from the solver band
  (`λ(fmax) / smallest_feature_mm`, honouring the project frequency unit). **Use this
  whenever a feature is small compared with the wavelength** — see below.
* Watch the message window for the edge-length ratio. A ratio in the thousands means
  a size mismatch in the geometry, not a mesh setting problem.

### Why `smallest_feature_mm` exists

Measured on a real task: a 50 mm cube sitting 2 mm above a 50 × 50 × 5 mm sheet, band
0–100 MHz.

```
λ at 100 MHz          = 3000 mm
edge length at 12/wl   ≈ 250 mm
smallest feature       = 2 mm          -> aspect ratio ≈ 125 : 1
```

The element size was two orders of magnitude larger than the feature to be resolved,
the matrix was badly conditioned, and the solver stopped with
`ERROR: Could not compute preconditioner.` Declaring
`smallest_feature_mm: 2.0` fixed it (FD `MinimumStepNumberTet` of 300 and of 1000 both
solved; a time-domain run with hexahedrals passed as a cross-check, proving the model
and port were sound and only the mesh was at fault).

**Engineering trade-off, not a bug.** With `expanded open` boundaries CST adds about a
quarter wavelength per side (750 mm at 100 MHz), giving a ~1550 mm domain. Resolving a
2 mm gap across that domain needs millions of elements; measured attempts with
`MinimumStepNumberTet` of 50 and 300 ran for minutes with no output. A tight,
explicitly sized boundary box solved in 2.77 s. When "resolve the small feature" and
"use an open λ/4 domain" conflict at low frequency, the options are to narrow the
band, use symmetry planes, or refine locally in the GUI. **This last option was not
verified here.**

## Monitors

```
cst_add_monitor_tool {"name": "farfield_2400", "field_type": "Farfield", "frequency": 2.4}
cst_add_monitor_tool {"name": "efield_2400", "field_type": "Efield", "frequency": 2.4,
                      "plane_normal": "z", "plane_position": 0.0}
cst_list_monitors_tool {}
```

Aliases accepted for `field_type`: `farfield`/`far`, `e`/`efield`/`electric`,
`h`/`hfield`/`magnetic`, `powerflow`/`poynting`, `current`/`currentdensity`,
`powerloss`/`loss`, `eenergy`/`energy`, `henergy`, `fieldsource`, `spacecharge`.

Vocabulary trap: the CST **`Monitor`** object uses `"Efield"`, `"Hfield"`,
`"Farfield"`; the separate **`TimeMonitor`** object uses `"E-Field"`, `"B-Field"`.
Mixing them silently produces the wrong monitor. The tool restricts you to the
`Monitor` vocabulary on purpose.

Monitor indices in CST are **0-based** — a query loop must run `0 .. n-1`.

`plane_position` only applies when `plane_normal` is also given (CST's own
documentation says so); supplying it alone is silently ignored, which matches CST.

---

## Related documents

* [Solver selection and band](solver-and-band.md) — the band a port cutoff must sit below
* [Solve, verify, evidence](solve-verify-evidence.md) — the checks that catch a bad port
* [Worked example](worked-example.md) — these settings in a runnable sequence
* [What CST 2026.2 does not expose](../../../docs/use/cst-2026-limits.md) — the absent mesh commands, in the project docs
