# Differences from the upstream CST MCP

> **Documentation index** › Reference › Differences from upstream

This package is a **refactor** of the CST MCP that ships inside
[`Cai-aa/CAE-Agent-Hub`](https://github.com/Cai-aa/CAE-Agent-Hub), under `MCP/CST/`.
That project is MIT-licensed (`Copyright (c) 2026 Thompson Labs`) and its notice is
retained in [`LICENSE`](../../LICENSE).

This page records what changed. Every figure was read from the upstream tree; nothing
here is a claim about which project is better, only about what is different.

---

## At a glance

| | Upstream `MCP/CST/` | This package |
| --- | --- | --- |
| MCP tools | **51**, all defined in one 623-line `mcp_server.py` | **84 across 14 categories**, in a `cst_mcp/` package; `mcp_server.py` is 237 lines |
| Layout | 6 flat top-level modules | `cst_mcp/` with `session`, `lint`, `registry`, `config`, `vba/` and `tools/` (9 modules) |
| Vendored runtime CLI | 824 files under `vendor/` | none — the `cst_runtime_*` / `cst_toolbox_*` family is served by a built-in command registry |
| Installation check | — | `check_install.py`, 598 lines: `--quick` / `--fix` / `--list-installs` |
| Offline checks | — | 9 suites that run with no CST installed |
| Tests | 5 files, ~11 KB | 36 Python files: offline gates, live runners, curated evidence |
| CI | none for this component (the hub's single workflow covers a different one) | GitHub Actions running every offline gate on Python 3.10 **and** 3.12 |
| Documentation | one README (197 lines) | 17 documents, progressive disclosure, plus `AGENTS.md` documentation-sync policy |
| Agent skills | kept at the hub root, not shipped with the MCP | 2 skills bundled in `skills/` (17 files) |
| Tool manifest | — | `docs/mcp_tools.json`, machine-readable, plus `cst_tool_manifest_tool` |
| Repository files | LICENSE, `.env.example`, `.gitignore`, `pyproject.toml`, READMEs | plus CHANGELOG, CONTRIBUTING, SECURITY, `.gitattributes`, issue forms and a PR template |

---

## Behaviour added on top

### Guard rails that refuse a command before CST sees it

`cst_mcp/lint.py` rejects a history block containing `StoreParameter`,
`StoreParameters`, `StoreDoubleParameter` or `Rebuild`. Upstream forwards such a block,
and CST 2026.2 answers

```
(&H8000FFFF) The rebuild operation cannot be used inside a structure macro.
```

In testing that left the Design Environment **permanently unresponsive** — every later
call hung. The linter also validates parameter **names** as plain identifiers, because
the name is interpolated into the `StoreParameters` array and a quote in it is a VBA
injection point.

### Mesh sizing from the smallest feature

`cst_set_mesh_tool` accepts `smallest_feature_mm`, deriving the minimum step count from
the feature size and the solver band. Without it a thin gap is meshed for the wavelength
and the frequency-domain solver stops at `Could not compute preconditioner.` Upstream:
none — element size there follows the wavelength alone.

### Project overwrite that does not strand a results directory

`cst_save_project_tool` takes `overwrite`; upstream: none. The implementation also closes
whatever project still occupies the target path first, because `Model/` and `Result/` stay
locked while it is open; deleting only the `.cst` leaves the companion directory behind and
CST refuses with `The project directory … already exists and is non-empty.` —
interactively, the prompt that stalls an unattended loop.

### A tool that exists to explain a missing capability

`cst_generate_mesh_tool` always raises, with the reason: CST 2026.2 has no standalone
mesh-generation command (17 spellings were tested). Without it a model retries a command
that can never work. Upstream: none.

### A port verdict, not just port numbers

`cst_read_port_info_tool` returns a verdict. A waveguide port placed on a 1.6 mm
microstrip cross-section had a **51.9 GHz** cutoff and a **6.2 kΩ** wave impedance at
2.4 GHz, so the S-parameters were referenced to 7623 Ω instead of 50 Ω and S11 was a flat
−0.6 dB line that is easy to mistake for an antenna. The solver had reported success.

---

## What was kept from upstream

The tool contract and the CST-facing mechanics (`cst.interface` / `cst.results` usage),
the parameter-sweep family (`cst_automation.py`, `cst_parameter_sweep.py`,
`cst_schematic.py`) and the Design Studio / schematic support all originate upstream and
keep their names and arguments, so an existing caller keeps working.

The CST **skills** originated as the `Skill/CST/` set in the same hub; here they are
reorganised into two question-oriented skills and shipped with the package.

---

## Related documents

* [Verification](../dev/verification.md) — the checks this package ships with
* [Failures hit during development](../../tests/evidence/known_failures.md) — the raw CST errors behind the guard rails
* [Known limits](../use/known-limits.md) — what this package does not do
* [What CST 2026.2 does not expose](../use/cst-2026-limits.md) — the other half of the limits
* [Layout](../dev/layout.md) — the repository tree
