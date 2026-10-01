# Failures hit during development (with raw errors and conclusions)

> This file records **failures that really happened during development / verification**, for later tracing.
> It differs from `mcp_calls_123.jsonl` (produced by re-running `tests/run_123_task.py`): that log keeps only the **final successful** run,
> while this file keeps the pitfalls hit before that success.
>
> Every conclusion comes from measurements on CST Studio Suite 2026.2 (on this machine, `C:\Program Files\CST Studio Suite 2026`),
> not from guesswork. Anything not measured is marked "unverified".

---

## Failure 1 — `cst_generate_mesh_tool` could never have succeeded

**Severity: high (tool permanently unusable + pollutes solver results)**

### Raw error
```
CSTError: RuntimeError: An error occurred while trying to execute _execute_vba_code:
Error in VBA code:
Sub Main
Mesh
End Sub

Default property usage is invalid.
(Mesh)
```

### Why this is not "a wrong parameter"
The tool emits a **bare `Mesh` statement**. To confirm that this is "the command does not exist" rather than "the syntax is wrong", each candidate form was measured one by one:

| Attempt | Result |
|---|---|
| `Mesh` | ✗ `Default property usage is invalid` |
| `Mesh.Create` | ✗ `Method or property not found` |
| `Mesh.Reset` | ✗ `Method or property not found` |
| `Mesh.CreateMesh` | ✗ |
| `Mesh.StartMeshing` | ✗ |
| `Mesh.GenerateMesh` | ✗ |
| `Mesh.AdaptiveMeshing` | ✗ |
| `Mesh.SetMeshType` | ✗ |
| `Mesh.Name` | ✗ |
| `MeshGeneration` | ✗ |
| `Call Mesh` | ✗ |
| `x = Mesh` | ✗ |
| `Model3D.Mesh` | ✗ |
| `MeshAdaption3D.Reset` | ✗ |
| `MeshAdaption3D.Create` | ✗ |
| `MeshAdaption3D.Start` | ✗ |
| `MeshSetup.Create` | ✗ (`MeshSetup` = `Empty`) |
| `MeshShapes.Create` | ✗ |

**Every Mesh method** listed in CST's official VBA reference `special_vbamesh\special_vbamesho.htm` (110 KB) was extracted and checked against this; they are settings only:

```
MeshType · LinesPerWavelength · MinimumStepNumber · MinimumStepNumberTet
MinimumStepNumberSrf · StepsPerWavelengthTet · DelaunayOptimizationLevel
CurvatureRefinementFactor · MaterialRefinementTet · EnrichSurfaceMesh ...
```

### Conclusion
**The VBA API of CST 2026.2 has no ability to "generate a mesh on its own"**; the mesh is built by the solver.
So this capability is **not something the MCP forgot to write — it does not exist underneath, and cannot be filled in**.

### Collateral damage (worse than "unusable")
The failure leaves an `ERROR:` line in the CST message window. Both `cst_run_solver_tool` and
`cst_generate_mesh_tool` call `session.error_messages()` to read that window, so this
stale ERROR gets **charged to the following solve**, making people misjudge the solve as failed. It happened on the very first full-chain run:

```
ERROR: Error in Script Execution: Expecting an already dimensioned array. (...)
ERROR: Default property usage is invalid. (Mesh)
ERROR: Could not compute preconditioner.
```

The first two are actually **leftover messages from earlier**, not produced by this solve.

### Handling
- the tool now `raise`s, explaining that CST has no such capability and what to do instead;
- the step was removed from `verify_live.py` and from the workflows of the two skills;
- a new `tests/check_docs_consistency.py` gate: treating this tool as a callable step in the docs is judged FAIL.

---

## Failure 2 — `Could not compute preconditioner.` (the real blocker of this task)

**Severity: high (the task cannot be completed without fixing it)**

### Raw error
```
ERROR: Could not compute preconditioner.
ERROR: 1 error and 3 warnings occurred.
```
**Note: the words "Not enough memory" are absent** — this is the key to telling the two kinds of failure apart.

### Isolation experiments (to rule out wrong guesses)

| Hypothesis | Experiment | Result |
|---|---|---|
| fmin=0 (frequency band includes DC) makes the matrix singular | change fmin to 0.001 | ✗ still fails |
| the dispersion model of the Iron material is wrong | replace the box with PEC | ✗ still fails |
| the port / geometry itself is invalid | cross-check with the time domain hexahedral solver | ✓ **passes** → the model and the port are completely correct |
| **the mesh does not resolve the 2 mm gap** | add `MinimumStepNumberTet` | **✓ the true cause** |

### Root cause analysis
```
band 0–100 MHz  →  λ = c/f = 3 m = 3000 mm
StepsPerWavelengthTet = 12  →  element edge length ≈ 250 mm
smallest feature of the model (the air gap between box and sheet) = 2 mm
                            →  aspect ratio ≈ 125 : 1
```

The element size is two orders of magnitude larger than the feature that must be resolved, so the matrix condition number is extremely poor and the preconditioner cannot be constructed.

### Handling
A new **`smallest_feature_mm`** input was added to `cst_set_mesh_tool`: you give the smallest feature size
of the model, and the tool back-computes the required minimum step number from `λ(fmax) / smallest_feature_mm` (taking the project frequency unit into account).

Measured (**without** the `expanded open` boundary):

| Configuration | Result |
|---|---|
| FD, `MinimumStepNumberTet = 300` | ✓ succeeds |
| FD, `MinimumStepNumberTet = 1000` | ✓ succeeds |
| TD hexahedral (cross-check) | ✓ succeeds |

### One engineering trade-off that was not solved (recorded honestly)
With the boundary set to `expanded open`, about λ/4 = 750 mm is added per side, giving a domain size of about 1550 mm.
Resolving the 2 mm gap then needs **millions of elements**. Measured:

| `MinimumStepNumberTet` | Result |
|---|---|
| 300 | runs for several minutes with no output (`modeler` holding only 62 MB, 8 s CPU → stuck in the meshing stage) |
| 50 | also several minutes with no output |

**"Resolving the 2 mm gap" and "a wide λ/4 open domain" conflict with each other at 0–100 MHz**; this is a trade-off between physics and compute,
not a software defect. The final delivery used a tightened explicit `open` boundary (converged in 2.77 s).
If an open boundary is mandatory, the feasible routes are narrowing the frequency band, using symmetry planes, or doing local mesh refinement inside the GUI.
**This one was not verified further.**

---

## Failure 3 — wrong `GetUnit` syntax (a defect I introduced myself in the previous round)

**Severity: medium**

### Raw error (only exposed at solve time)
```
ERROR: Error in Script Execution:
Expecting an already dimensioned array.
(u = GetUnit ("Frequency"))
```

### Key points
- this code was **written in the previous round, when I added `read_frequency_unit()`** — a defect I introduced myself;
- it **only errors during a solve**: calling it directly through `cst_run_vba_tool` does not error,
  so the previous round's verification did not catch it;
- the error text is captured by `cst_run_solver_tool` and mixed into the solve-failure message, making it easy to misread as a solver fault.

### Measured fix

| Form | Result |
|---|---|
| `u = GetUnit ("Frequency")` | ✗ Expecting an already dimensioned array |
| `u = GetUnit$("Frequency")` | ✗ |
| `u = GetUnit("Frequency")` (no space) | ✗ |
| `u = Units.GetUnit ("Frequency")` | **✓ correct** |
| `Units.GetUnit$("Frequency")` | ✗ |

**The `Units.` prefix is mandatory.** By contrast `Units.SetUnit("Frequency","MHz")` may be written without the prefix —
the two are asymmetric, which makes it easy to misremember. `read_frequency_unit()` has been fixed, and `read_solver_band()` was added
(using the same qualified form) for the mesh step-number computation.

---

## Failure 4 — `A command is used in the wrong thread context` (judged a usage problem, not a tool defect)

**Severity: medium, but the conclusion is "an environment problem"**

### Raw error
```
VBA command processing failed.
A command is used in the wrong thread context.
This very likely the cause of a RunScript command,
that is trying to update the history list.
Nested macro calls are currently not supported.
```
The triggering statement is what `cst_define_parameters_tool` produces:
```vba
Sub Main
MakeSureParameterExists "L", "50"
...
Rebuild
End Sub
```

### Control experiments (the key to judging its nature)

| Condition | `MakeSureParameterExists` | `StoreParameters` | Conclusion |
|---|---|---|---|
| new project, no geometry | ✓ | ✓ | normal |
| new project, **with** a history tree (containing solids) | ✓ | ✓ | normal |
| **reusing a Design Environment left behind by another client** | **✗ errors** | not tested separately | **this is the problem** |

The very same command block is completely normal in a new project, and fails only when an old DE is reused.

### Conclusion and handling
**The tool is not written wrongly — it is the calling pattern**: a Design Environment left behind by an earlier script was reused,
and its thread context no longer belongs to the current client.

The handling is to add `cst_quit_tool` at the start of the flow (closing every project and releasing the DE), then
`cst_connect_tool` to create a clean DE. **It passed without changing any tool code**, and the final 30 calls were all green.

`cst_quit_tool` itself had also been fixed in an earlier round: the original closed only the "currently active project",
so the `modeler_AMD64.exe` of the leftover projects (about 700 MB each) was not released, and once enough of them accumulated they caused a genuine
`Not enough memory`. After the fix, all 3 projects were measured to close and the DE was released with them.

---

## Failure 5 — the other source of `Default property usage is invalid`: misleading leftover messages

**Severity: medium (misleading diagnosis)**

On the first full-chain run, the solve "failure" message contained three ERROR lines at once:

```
ERROR: Error in Script Execution: Expecting an already dimensioned array. (u = GetUnit ("Frequency"))
ERROR: Default property usage is invalid. (Mesh)
ERROR: Could not compute preconditioner.
```

The first two are **not produced by this solve**; they are old messages left in the CST message window by the earlier
`cst_generate_mesh_tool` and by my `GetUnit` code, read out together by `error_messages()`.

`session.error_messages()` earlier had an even worse defect of the same kind: it matched **any message whose body contains
the word "error"**, so the transient solver's normal
`The steady state error limit was reached.` was also reported as an error. That defect was fixed in the previous round to
**judge by message type only**.

### Lesson (already written into the gate)
The message window **accumulates across calls**. When reading errors you must separate "newly produced by this operation" from "left over from before".
The current approach hands `messages_tail` to the caller honestly and documents this risk in the docs;
**"take only the messages newer than this operation" is not implemented yet** (an unverified approach: compare the message count before and after the operation).

---

## Failure 6 — a BOM in `.env` breaks the first key (hit on installation day)

**Severity: medium (`check_install.py` reports a false failure, and only the first key is affected, which makes it very easy to misjudge)**

### Symptom
After extending the file checks in `check_install.py`, full mode produced one isolated failure:

```
  [FAIL] CST_INSTALL_ROOT  not set - edit .env, or run: python check_install.py --fix
  passed : 49   warning: 0   failed : 1
RESULT: NOT READY
```

`.env` plainly contains `CST_INSTALL_ROOT=C:\Program Files\CST Studio Suite 2026`,
`Test-Path` also confirms the path exists, **and `CST_DESIGN_ENVIRONMENT_EXE`
in the same file is PASS**.

### Root cause
The `.env` was written in a way that carries a BOM (PowerShell `Set-Content -Encoding UTF8` writes a BOM,
**and Notepad does so by default too**). Read as `utf-8`, the BOM stays on the first key:

```
'\ufeffCST_INSTALL_ROOT' != 'CST_INSTALL_ROOT'
```

So **only the first key of the file** can never match, while every later key is completely normal. This is why "the key is plainly written yet reported as not set",
and it is the kind of problem most easily misjudged as "the user configured it badly".

### Handling
`parse_env()` now reads as `utf-8-sig`, with a second-line `lstrip("\ufeff")` on the key name as well.
After the fix, with the same BOM-carrying `.env`:

| Mode | Before the fix | After the fix |
|---|---|---|
| `--quick` (with `.env`) | 36 passed / 1 failed | **44 passed / 0 failed** |
| full (with `.env`) | 50 passed / 1 failed | **58 passed / 0 failed** |

### Documentation figures corrected along the way
The docs had long said `check_install.py` was **37/37**; that was the figure from an earlier version with fewer checks.
It was measured this time and corrected to: **`--quick` 44/44, full 58/58**; without a configured `.env` it is
**30 passed / 2 warning / 3 failed** (those 3 FAILs are expected, see section 0 of the installation guide).

---

## Failure 7 — parameter sweep: the execution channel + one CST behaviour limit

**Severity: high (without a fix, every case fails)**

The first real run after porting the sweep feature (`L = 48:52:2`, 3 cases) **failed all three cases, each with a different error**:

| case | error |
|---|---|
| 1 | `The specified material does not exist: Iron` `(.Create)(Line:12)` |
| 2 | `A command is used in the wrong thread context / Nested macro calls are currently not supported` |
| 3 | `The message (_execute_vba_code) cannot be dispatched: Connection has been closed!` |

### Problem 1 — `CSTSessionManager.connect()` does not launch CST

```
RuntimeError: No DEs found to connect to.
```

It only connects to an **already existing** Design Environment. Changed to "connect if you can, launch only if you cannot", avoiding opening CST repeatedly:

```python
manager = CSTSessionManager()
try:
    manager.connect(launch_if_needed=False)
except Exception:
    manager.connect(launch_if_needed=True)
```

### Problem 2 — the parameter-changing VBA **must not** go through `add_to_history`

The original `_case_vba` handed `StoreParameters` + `Rebuild` to `add_to_history`. Measured results for three forms:

| Form | CST's answer |
|---|---|
| bare block → `add_to_history` | `The rebuild operation cannot be used inside a structure macro.` — and it **can hang the Design Environment** |
| `Sub Main` block → `add_to_history` | `Unterminated block ... in add_to_history` |
| bare block → `execute_vba` | **succeeds** (it adds `Sub Main` itself and calls `_execute_vba_code`) |

Fix: `_case_vba` generates a bare block, and the call site became `self.manager.execute_vba(_case_vba(case))`.

### Problem 3 — library materials are not saved with the project (**unsolved, this is CST behaviour**)

This is the **true root cause** of all three cases failing, and it has nothing to do with the sweep code:

```
MaterialLibrary.LoadMaterialFromLibrary ("Iron", "", True)
```

A loaded material is **not persisted into the `.cst`**. After saving, reopening the project and triggering a rebuild fails at the solid that uses that material:

```
(&H8000ffff) The specified material does not exist: Iron
(.Create)
```

**Changing a parameter necessarily triggers a rebuild** ⇒ **running a parameter sweep on any project that uses a library material fails every case.**

Isolation experiments (measured):

| Scenario | Result |
|---|---|
| new project → change parameter → add geometry → change parameter again | **all succeed** |
| save → reopen → change parameter (library material) | **fails** (the rebuild cannot find the material) |
| send only `StoreParameters`, no rebuild | succeeds, the parameter reads back, but the geometry does not change |
| a separate `Rebuild` afterwards | fails (`wrong thread context`), and CST may hang afterwards |

**Danger**: the parameter value **really is written in**, so "`StoreParameters` succeeded" **cannot** be taken as evidence that the case succeeded.

Written into `skills\cst-studio-suite-mcp\references\guard-rails-and-limits.md` (Known limits)
and `references\workflow.md` (Parameter study flow).

---

## Summary

| # | Symptom | Nature | Fixed? | Impact |
|---|---|---|---|---|
| 1 | `Default property usage is invalid. (Mesh)` | **CST has no such API**, cannot be filled in | changed to an honest error | tool permanently unusable, and it pollutes solver results |
| 2 | `Could not compute preconditioner.` | **not enough capability** (the mesh cannot resolve the small feature) | `smallest_feature_mm` added | the task cannot be completed without the fix |
| 3 | `Expecting an already dimensioned array. (GetUnit)` | **a code defect I introduced** | fixed | only exposed at solve time, easily misjudged as a solver fault |
| 4 | `wrong thread context` | **a usage problem**, not a tool defect | no code change; a clean DE is used instead | makes people think the tool is broken |
| 5 | leftover ERRORs mixed into the solve results | **misleading diagnosis** | partly fixed (type judging fixed) | misjudges the solve as failed |
| 6 | a BOM in `.env` breaks the first key | **a parsing defect** (Notepad alone triggers it) | fixed (`utf-8-sig`) | a false failure right at install, easily misjudged as the user not configuring it |
| 7 | wrong sweep execution channel + library materials not persisted | **1 code defect + 1 CST behaviour limit** | channel fixed; the material limit written into the docs | every case fails, and the parameter value is still written in, which is highly misleading |

**The accurate public statement**:
- capability the MCP is missing: **1** (CST has no API to generate a mesh on its own; it cannot be filled in);
- what had to be changed in a tool to complete the task: **1** (`cst_set_mesh_tool`);
- defects in our own code: **2** (the `GetUnit` syntax in `read_frequency_unit`, the BOM handling in `parse_env`);
- judged a usage / environment problem, with no code change: **1** (the thread context of `cst_define_parameters_tool`).

---

## Evidence notes

The raw error texts in this file come from the live output of the development session. The messages relating to failures 1, 2, 3 and 5 also appear in
the following per-run logs, which are not committed but are regenerated by re-running the corresponding runner:

- `tests/evidence/live_verification.jsonl` — the full-chain run log; produced by re-running `tests/verify_live.py`;
- `tests/evidence/verify_fixes_live.log` — the targeted fix-verification log; produced by re-running `tests/verify_fixes_live.py`;
- `tests/evidence/mcp_calls_123.jsonl` — the final 30 successful calls (**excluding** the failures above); produced by re-running `tests/run_123_task.py`.

The **mesh step-number scan** and the **`GetUnit` syntax matrix** for failures 2 and 3 came from one-off probe scripts;
the scripts themselves were not kept (deleted during cleanup), and what is recorded here is the measured conclusion from that time.
To re-check, run `tests/probe_commands.py` (single CST command probing) and reproduce it yourself.

---

## Related documents

* [Verification](../../docs/dev/verification.md) — the runs these failures were hit during, and what each one proves
* [What CST 2026.2 does not expose](../../docs/use/cst-2026-limits.md) — which of these failures are CST's own API limits, not server defects
* [Known limits](../../docs/use/known-limits.md) — the limits this server carries as a result
* [MCP tool-call record for 123.cst](mcp_calls_123_report.md) — the per-call record of the clean run that followed
* [CST Studio Suite MCP skill](../../skills/cst-studio-suite-mcp/SKILL.md) — the skill that sends an agent here first when diagnosing
