# Layout

> **Documentation index** › Layout

```
CST-MCP/
├─ mcp_server.py                 MCP entry point, registry bootstrap, manifest builder
├─ check_install.py              install self-check: --quick / --fix / --list-installs
├─ cst_automation.py             Design Environment bridge used by the sweep family
├─ cst_schematic.py              schematic (DS) project support
├─ cst_parameter_sweep.py        per-case project copies, parameter application, sweeps
├─ cst_mcp/
│  ├─ config.py                  .env loading, CST paths, workspace/evidence folders
│  ├─ session.py                 CSTSession: Design Environment, projects, VBA, results
│  ├─ lint.py                    guards for history blocks and parameter values
│  ├─ registry.py                extensible tool registry
│  ├─ vba/geometry.py            VBA block builders with verified method names
│  └─ tools/                     one module per category; each exposes register_tools()
│     ├─ session_tools.py        projects, messages, raw VBA, history blocks
│     ├─ parameter_tools.py      read/create/change/delete design parameters
│     ├─ geometry_tools.py       primitives, boolean, transform, extrude, components
│     ├─ material_port_tools.py  materials and ports
│     ├─ simulation_tools.py     solver choice, frequency range, boundary, mesh, monitors
│     ├─ result_tools.py         result tree, verification readouts, exports
│     ├─ sweep_tools.py          parameter sweep: preview and run
│     └─ runtime_tools.py        built-in cst_runtime_* / cst_toolbox_* command family
├─ skills/                       one directory per skill: SKILL.md + metadata.json
│  │                            + agents/openai.yaml + references/*.md
│  ├─ cst-studio-suite-mcp/      modes, defaults, templates, tool order, validation
│  └─ cst2026-simulation-execution/  verified values, port/mesh defects, result checks
├─ docs/
│  ├─ README.md                  grouped documentation index
│  ├─ mcp_tools.json             machine-readable manifest of all 84 tools
│  ├─ start/                     installation and upgrade
│  ├─ use/                       quick start, usage, tools, rules, limits
│  ├─ extend/                    adding tools and tool families
│  ├─ dev/                       layout, skills, verification
│  └─ reference/                 design records and evaluations
├─ test_demo/
│  ├─ README.md                  what the demo project is for
│  └─ test_demo.cst              self-contained demo project for install verification
├─ tests/
│  ├─ smoke_registry.py          offline: registry + manifest
│  ├─ check_mcp_compliance.py    offline: MCP protocol checks
│  ├─ check_self_description.py  offline: workflow, summaries, examples self-consistent
│  ├─ check_skill_tool_refs.py   offline: every tool named in a skill exists
│  ├─ check_skill_layout.py      offline: skill directory layout (SKILL.md + refs)
│  ├─ check_docs_consistency.py  offline: documented tools/examples are real and usable
│  ├─ test_audit_regressions.py  offline: regression tests for every fixed bug
│  ├─ test_port_info_verdict.py  offline: port-verdict threshold regression tests
│  ├─ test_save_overwrite.py     offline: project-overwrite path regression tests
│  ├─ verify_live.py             live CST: full chain
│  ├─ verify_fixes_live.py       live CST: targeted verification of fixed tools
│  ├─ verify_task_123.py         live CST: the worked task, with per-call logging
│  ├─ run_123_task.py            live CST: a complete worked task, copy-and-adapt
│  ├─ verify_sweep_geometry.py   live CST: sweep without solving
│  ├─ verify_sweep_solve.py      live CST: sweep with solving
│  ├─ probe_commands.py          probe individual CST VBA commands
│  ├─ diagnose_failures.py       focused diagnosis of a failing tool
│  ├─ bt_*.py, s11_report.py     development scratch, one machine and one project:
│  │                             the record behind tests/evidence/known_failures.md.
│  │                             Neither gates nor documented runners.
│  └─ evidence/                  curated records; per-run logs are regenerated on demand
├─ .env.example                  configuration template (`.env` is never committed)
└─ pyproject.toml                packaging metadata
```

Per-run output (`.log`, `.jsonl`, exported `.s1p`/`.txt`) is written under
`tests/evidence/` but is **not** committed — see [Verification](verification.md).

---

## Related documents

* [Skills](skills.md) — the two bundled agent skills
* [Verification](verification.md) — the checks and the committed evidence
* [Repository README](../../README.md) — the documentation index
