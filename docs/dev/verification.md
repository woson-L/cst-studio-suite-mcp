# Verification

> **Documentation index** › Verification


**Start here — one command that answers "is this installed correctly?"**

```powershell
python check_install.py
```

It checks, in order: the Python version and the `mcp` / `pydantic` packages; the
server files and tool modules; `.env` and whether every path in it exists *on
this machine*; the tool registry; a real MCP handshake over stdio with
`tools/list` (exactly what the model's client does); and optionally a live
`cst_health_check_tool` + `cst_connect_tool` against CST. Exit codes: `0` ready,
`1` warnings, `2` problems.

Options:

| Command | Use |
| --- | --- |
| `python check_install.py` | full check, changes nothing |
| `python check_install.py --quick` | skip CST and the MCP handshake (fast, works before CST is installed) |
| `python check_install.py --fix` | detect CST on this machine and write `.env` |
| `python check_install.py --list-installs` | just show the CST installations found |

Deeper tests:

| Test | Needs CST | Result on the reference machine |
| --- | --- | --- |
| `python check_install.py` | yes | **60/60** passed (46/46 in `--quick`) |
| `python tests/smoke_registry.py` | no | 84 tools registered, no duplicate names, manifest generated |
| `python tests/check_mcp_compliance.py` | no | **17/17** MCP protocol checks passed |
| `python tests/check_self_description.py` | no | 0 problems |
| `python tests/check_skill_tool_refs.py` | no | 0 missing references |
| `python tests/check_skill_layout.py` | no | 0 problems |
| `python tests/check_docs_consistency.py` | no | 0 problems |
| `python tests/test_audit_regressions.py` | no | **63/63** checks passed |
| `python tests/test_save_overwrite.py` | no | **14/14** checks passed |
| `python tests/test_port_info_verdict.py` | no | **13/13** checks passed |
| `python tests/verify_live.py` | yes | **82/82** checks passed against live CST 2026.2 |
| `python tests/verify_fixes_live.py` | yes | **28/28** targeted checks passed |
| `python tests/run_123_task.py` | yes | 30 tool calls, 0 failed |

The rows marked *no* run in CI on every push — see
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml). The count in
`check_install.py` is environment-dependent (a machine without CST reports fewer
checks), so treat the two totals as a reference point, not a target.

All runners write a JSONL progress file, so an interrupted run still leaves a
usable log. Those per-run logs are machine-specific and are **not committed**
(`.gitignore` excludes `*.log`; the JSONL trails are produced on demand under
`tests/evidence/`). What is committed is the curated record:

| File | Content |
| --- | --- |
| `known_failures.md` | **the failures hit during development, with raw CST errors and conclusions** |
| `mcp_calls_123_report.md` | the 30 calls of the worked task, human-readable |
| `mcp_compliance.json` | protocol check results |
| `result_summary.json` | what `cst_write_summary_json_tool` produces |

Re-running `verify_live.py`, `verify_task_123.py`, `run_123_task.py` or
`verify_fixes_live.py` regenerates the full per-step logs (payloads, Touchstone
and ASCII exports) alongside these files.

What the live run proved:

* the whole chain runs through MCP — health, project, parameters, geometry,
  materials, port, solver choice, frequency range, boundary, mesh, monitors,
  solve, result reading, export;
* the frequency domain solver **converged**
  (`All broadband sweep convergence criteria have been satisfied`) and produced
  `S1,1` with `ZRef = 50 + 0j` across all 1001 points;
* a Touchstone `.s1p` and an ASCII export were written;
* the guard rails fire: a history block containing `StoreParameters` is rejected
  before CST sees it, an unknown solver name is refused, an out-of-range
  accuracy is refused, a cone with both radii zero is refused, a parameter *name*
  containing a quote is refused (VBA injection), and a solve is refused up front
  when free RAM is below the threshold.

Reference numbers from that run (deliberately arbitrary geometry — this was a
capability test, not a design exercise): with `Lpatch = 27 mm`,
`dinset = 21.6 mm` on 1.6 mm FR-4, S11 is −15.4 dB at 2.56 GHz and −4.3 dB at
2.4 GHz; total efficiency 28.4 % at 2.4 GHz. All values are quoted from the
exported files.

Verified against **CST Studio Suite 2026.2**
(`_cst_results` 2026.2 Release from 2025-11-28).

## Overwriting a project without a confirmation

Iterative runs hit this on every round: the working copy is saved back onto its own
path, and CST asks about the previous results. Measured on the live build, with
throwaway projects:

| Attempt | Result |
| --- | --- |
| `save(path)` onto an existing project | `Failed to save project. The given path already exists <file>` |
| delete only the `.cst`, then `save(path)` | `Failed to save project. The project directory <dir> already exists and is non-empty. It would be overwritten.` — the companion directory and its results are still there |
| `save(path, allow_overwrite=True)` while the old project is **open** | bare `Failed to save project` — `Model/` and `Result/` are locked |
| close the old project, then `save(path, allow_overwrite=True)` | **succeeds**, no prompt; CST replaces the `.cst` and the companion directory itself |
| the same, repeated | succeeds again (idempotent) |

So the rule `cst_save_project_tool {"overwrite": true}` implements is: close whatever
occupies that path, then let CST do the overwrite. The server never deletes project
files itself — the earlier "delete the `.cst` first" workaround was what produced the
orphaned directory in the first place.

---

## Related documents

* [Known failures](../../tests/evidence/known_failures.md) — the raw CST errors behind these results
* [Contributing](../../CONTRIBUTING.md) — which of these checks to run before a pull request
* [Layout](layout.md) — where the runners and the committed evidence live
* [Skill set](skills.md) — the two skills the skill-reference checks cover
* [What CST 2026.2 does not expose](../use/cst-2026-limits.md) — read before diagnosing a failure as a server bug
