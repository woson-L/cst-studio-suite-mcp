---
name: cst2026-simulation-execution
description: Use this skill when you must actually run a CST Studio Suite 2026 simulation through the CST MCP - choose and configure a solver, set the frequency range, place ports, size the mesh, add monitors, solve, and prove the result is physically meaningful. Contains the exact command strings and enum values verified on CST 2026.2, the port and mesh defects that silently produce meaningless S-parameters, and the readouts that catch them.
---

# CST 2026 Simulation Execution

This skill is the **execution-correctness layer**: the verified values, and how to tell a
real result from a plausible-looking wrong one.

Use **`cst-studio-suite-mcp`** for the operating mode, the defaults, the templates, the
tool catalogue and the call order — in short, to know *what to do and which calls to
make*. Use **this** skill for *which values are legal* and *whether the answer can be
believed*.

## The four checks that make a result quotable

A solver that exits successfully is **not** a simulation. Before quoting any number:

| # | Requirement | How to check |
| --- | --- | --- |
| 1 | The solver **converged** | `cst_messages_tool` shows `convergence criteria have been satisfied`, no `ERROR:` line |
| 2 | The **port mode propagates** in the band | `cst_read_port_info_tool`: cutoff well below `fmin` |
| 3 | The **reference impedance** is what you intended | `cst_read_reference_impedance_tool`: a discrete 50 Ω port must read `50+0j` |
| 4 | The **geometry is what you think** | `cst_model_audit_tool`: solids, materials, volumes |

If any is missing, the job status is `needs_validation`, not "done".

## Mandatory order

```
solver  ->  frequency range  ->  configure solver  ->  save  ->  solve  ->  verify
```

Solving without a frequency range fails with
`Solver run failed. Frequency range not set correctly.`

## Read only the reference file you need

- `references/solver-and-band.md` — solver choice, the three different "frequency
  ranges", and the full FD / TD / eigenmode configuration with every valid enum value.
- `references/ports-boundaries-mesh.md` — port types and placement, the two port
  defects that produce believable wrong S-parameters, boundary kinds, symmetry,
  background, mesh sizing (including why `smallest_feature_mm` exists), and monitors.
- `references/solve-verify-evidence.md` — the verification set, number handling,
  sanity checks, evidence export, and the full diagnosis table.
- `references/worked-example.md` — a copy-and-adapt end-to-end call sequence, a worked
  task with real measured numbers, and this skill's verification status.

## Non-negotiable rules

- **Parameters only via `cst_set_parameters_tool`.** Never put
  `StoreParameter`/`StoreParameters`/`Rebuild` in a history block: CST refuses it and
  it can leave the Design Environment permanently unresponsive.
- **There is no meshing step.** CST 2026.2 has no VBA command that builds the mesh; the
  solver does it. `cst_generate_mesh_tool` always raises and exists only to say so.
- **Declare small features.** If the model has a gap or thickness far smaller than the
  wavelength, set `cst_set_mesh_tool {"smallest_feature_mm": <value>}` or the solve
  stops at `Could not compute preconditioner.`
- **Quote numbers from exported files**, never from the screen.
  `S11_dB = 20*log10(abs(S11))`; **`Abs(E)` is not gain**.
- **Release CST when done** with `cst_quit_tool`. Each open project holds ~700 MB, and
  leaking them is what eventually causes `Not enough memory`.
- **Do not invent CST method names.** Everything here was measured on 2026.2. Where
  this skill says a command does not exist, it does not exist — do not hunt for a
  variant spelling.

---

## Related documents

* [Solver selection and band](references/solver-and-band.md) — solver choice, the three frequency ranges, every valid enum
* [Ports, boundaries and mesh](references/ports-boundaries-mesh.md) — the port defects that produce believable wrong S-parameters
* [Solve, verify, evidence](references/solve-verify-evidence.md) — the verification set and the diagnosis table
* [Worked example](references/worked-example.md) — an end-to-end call sequence with real measured numbers
* [CST Studio Suite through MCP](../cst-studio-suite-mcp/SKILL.md) — the companion skill for modes, defaults and call order
