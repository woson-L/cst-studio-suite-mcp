# What CST 2026.2 does not expose

> **Documentation index** › What CST 2026.2 does not expose


These are limits of CST's own automation API, not gaps in this server. Each was
verified against the live build; do not spend time hunting for a workaround.

| Task | Reality | Instead |
| --- | --- | --- |
| Generate / preview the mesh separately | **No such API.** The `Mesh` object is settings only (`MeshType`, `StepsPerWavelengthTet`, `MinimumStepNumberTet`, …). A bare `Mesh` statement gives `Default property usage is invalid`; `Mesh.Create`, `Mesh.Reset`, `MeshGeneration`, `MeshAdaption3D.Create` do not exist — 17 spellings tested | Use `cst_set_mesh_tool` for the settings, then `cst_run_solver_tool`; the solver meshes. `cst_generate_mesh_tool` exists only to explain this and always raises |
| Read the project frequency unit | `GetUnit ("Frequency")` fails with `Expecting an already dimensioned array`; `GetUnit$` does not exist | `Units.GetUnit ("Frequency")` — the `Units.` prefix is required, even though `Units.SetUnit` works without it |
| Target an existing project path with save | `save(path)` refuses: `Failed to save project. The given path already exists` — and there **is** an overwrite flag (`allow_overwrite`), contrary to what this table said before. Deleting only the `.cst` first is not a workaround: a project is the file *plus* a companion directory holding `Model/` and `Result/`, so the save then fails with `The project directory <dir> already exists and is non-empty. It would be overwritten.` — which interactively is the confirmation about the previous results | `cst_save_project_tool {"overwrite": true}` — it passes `allow_overwrite` and closes a project still occupying that path first |

**A feature far smaller than the wavelength must be declared**, or the solve stops at
`Could not compute preconditioner.` (note: no memory wording — that is a different
failure). Element size otherwise follows the wavelength alone: a 2 mm gap in a
0–100 MHz model meets a 3000 mm wavelength, and the resulting system cannot be
factored.

```
cst_set_mesh_tool {"mesh_type": "Tetrahedral", "smallest_feature_mm": 2.0}
```

---

## Related documents

* [Rules that keep results trustworthy](rules.md) — the working rules these findings produced
* [Known limits](known-limits.md) — limits of this server rather than of CST
* [Known failures](../../tests/evidence/known_failures.md) — the isolation experiments in full
* [Tool catalogue](tool-catalogue.md) — the tool to use instead, for each row above
* [Contributing](../../CONTRIBUTING.md) — how to report a limit with the evidence it needs
