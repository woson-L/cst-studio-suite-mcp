---
name: cst-studio-suite-mcp
description: >-
  Plan and drive CST Studio Suite 2026 through the CST MCP server. Use when an agent
  must operate CST through MCP tools - classify the request (plan only, new project,
  existing project, parameter study, optimization handoff), resolve missing inputs and
  defaults, pick a starting template, then model, assign materials, place ports, set
  boundaries / mesh / solver / frequency range / monitors, solve, validate results
  against the evidence rules, export artefacts and release CST. Also covers which CST
  MCP tools exist and in what order to call them.
---

# CST Studio Suite 2026 through MCP

This skill is the **decision and orchestration layer**: what to do, which tools to call,
in what order, with which defaults, and what evidence the answer must carry.

The server exposes **84 tools** across 14 categories and talks to CST's official
automation API (`cst.interface` / `cst.results`). Machine-readable companion:
**`docs/mcp_tools.json`** — every tool with its parameters, JSON schema, examples and
notes. Read that file for an exact signature; read this skill for the *order* and the
*rules*.

## This skill vs `cst2026-simulation-execution`

The two skills are complementary. They are split by question, not by tool:

| Question | Skill |
| --- | --- |
| What should I do? Which mode am I in? What may I default? | **this skill** |
| Which tool, in what order, with which arguments? | **this skill** |
| Is this result real? What is the cutoff, the ZRef, the mesh limit? | `cst2026-simulation-execution` |
| What exact enum values does this solver accept? | `cst2026-simulation-execution` |

Rule of thumb: come here to **build and run**, go there to **trust the number**.

## Step 0 — classify the request before touching CST

| Mode | Use when | Action |
| --- | --- | --- |
| **Plan only** | User asks for a scheme, script outline, or workflow | **Do not run CST.** Produce the setup plan, assumptions and expected outputs |
| **New project** | User wants a new CST case | Pick a template, resolve inputs, create a run project |
| **Existing project** | User gives a `.cst` path, or asks to modify the open project | Inspect first, then work on a **copy** unless told otherwise |
| **Parameter study** | User asks for ranges, cases, or a comparison | Enumerate the cases and show the count **before** solving |
| **Optimization** | User asks to improve S11, gain, bandwidth, coupling | Confirm objective, bounds and stopping rule first; hand off to the runtime helpers |

Record whether the task is destructive, expensive, or plan-only. For plan-only tasks do
not start CST — return the workflow, the assumptions, the expected outputs, and the MCP
tools that *would* be used.

Then follow **`references/workflow.md`**, which carries each mode through to release and
reporting.

## Input policy — ask once, then default

Ask **at most one** compact question, and only when a missing value would change the
simulation's meaning. If the user says "directly run", "use defaults" or "先默认", use
the defaults and record them in the report instead of pausing.

Critical inputs: **case type**, **target frequency or band**, **new vs existing
project**, **primary objective**, **whether to actually run the solver**.

Everything else is defaultable — units, background, metals, boundaries, solver choice,
mesh level, monitor frequencies, output set, run directory. The full default table, the
derived-geometry formulas and the defaults card template are in
**`references/parameter-policy.md`**.

State every defaulted value in the final report.

## Operating rules

* **Never overwrite a user's source `.cst`.** Copy it (with its companion folder) into a
  run directory unless the user explicitly asks for in-place edits.
* **Inspect before writing.** Read parameters, solids, materials, ports, solver, band,
  monitors and the result tree before changing anything.
* **Never rebuild an existing project from scratch** unless the user asks for a rebuild.
* **Save before solving**, and set the frequency range before solving.
* **Treat solver success as unverified** until result evidence confirms it.
* **Do not set the frequency range blindly.** Eigenmode workflows may not need
  `Solver.FrequencyRange`; the tool handles the unit correctly, but the band is still a
  physical choice.
* **Add monitors before solving** if monitor outputs are required.
* **Stop and ask** if several projects are open and the target is ambiguous.

## The five non-negotiable rules

1. **Parameters only through `cst_set_parameters_tool`.** Never put
   `StoreParameter`/`StoreParameters`/`Rebuild` in a history block — CST refuses it and
   it can leave the Design Environment permanently unresponsive.
2. **Save before solving, and set the frequency range first**, or the run fails with
   `Solver run failed. Frequency range not set correctly.`
3. **A successful solve is not a correct result.** Verify the reference impedance and the
   port cutoff before believing any S-parameter.
4. **Report numbers from exported files**, not from the screen.
   `S11_dB = 20*log10(abs(S11))`; **`Abs(E)` is not gain**. VSWR comes from `|Γ|`, not
   from dB.
5. **Release CST with `cst_quit_tool` when done.** Each open project holds ~700 MB and
   leaking them eventually causes `Not enough memory`.

## Two traps worth knowing before you start

* **There is no meshing step.** CST 2026.2 has no VBA command that builds the mesh on its
  own; the solver does it. `cst_generate_mesh_tool` always raises and exists only to
  document this. If the model has a feature far smaller than the wavelength, set
  `cst_set_mesh_tool {"smallest_feature_mm": <value>}` first, or the solve stops at
  `Could not compute preconditioner.`
* **A library material is renamed on load.** CST names the project material after the
  library entry, so `material_name` is applied as a `Material.Rename`. Use the returned
  `material` key when assigning it to a solid — not the library name.

## Validation and reporting status

Use these statuses consistently and never invent a stronger one:

| Status | Meaning |
| --- | --- |
| `validated` | Solver ran **and** the requested result evidence was found and parsed |
| `needs_validation` | Project or solver ran, but the requested evidence is missing or incomplete |
| `partial` | Some outputs validated, others failed or were not produced |
| `blocked` | A CST / MCP / licence / input problem prevented meaningful execution |
| `plan_only` | Planning or script generation was requested; nothing was executed |

A run is `validated` only with at least one concrete evidence source: a saved `.cst`, a
result-tree entry from `cst_list_results_tool`, an exported file, a readable 1D result,
or a solver log showing completion. If the solve command returns success but no evidence
exists, report `needs_validation` — not success.

## Read only the reference file you need

- `references/workflow.md` — the five operating modes end to end, the standard sequence,
  run directories, the report shape, and how to do parameter studies and optimization
  when the MCP has no sweep tool.
- `references/parameter-policy.md` — critical vs defaultable inputs, the default table,
  derived-geometry formulas, existing-project inspection, and the defaults card.
- `references/templates.md` — starting points (2.4 GHz patch, 77 GHz array, PEC cavity
  eigenmode, existing-project rerun) with default cards and dimension guidance.
- `references/tool-catalogue-and-order.md` — the 13 categories, all call steps with
  runnable arguments, the minimal working example, and the runtime/toolbox wrapper map.
- `references/result-validation.md` — evidence requirements and the per-quantity
  validation rules (S-parameters, VSWR, far field, near field, eigenmode, sweeps).
- `references/guard-rails-and-limits.md` — project/session safety, numerical correctness,
  the pitfalls the tools already handle, and the known limits of the CST API.
- `references/extending-and-conventions.md` — how to add a tool, and the conventions and
  gates a new tool must satisfy.

## When something fails

Read `tests/evidence/known_failures.md` in the CST-MCP package first — it records the
failures already hit, with raw CST errors, the isolation experiments, and the
conclusions. Then `references/guard-rails-and-limits.md` for the diagnosis table.

---

## Related documents

* [Workflow by operating mode](references/workflow.md) — the operating modes end to end, from preflight to release
* [Parameter policy](references/parameter-policy.md) — what to ask once, what to default, what to derive
* [Result validation](references/result-validation.md) — the evidence and status a report must carry
* [CST 2026 simulation execution](../cst2026-simulation-execution/SKILL.md) — the companion skill for legal values and trust checks
* [Documentation index](../../docs/README.md) — the project documentation, grouped by task
