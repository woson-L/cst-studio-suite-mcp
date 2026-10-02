# CST-MCP — CST Studio Suite 2026 through the Model Context Protocol

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-stdio-6E4AFF.svg)](https://modelcontextprotocol.io)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](#requirements)
[![Tools: 84](https://img.shields.io/badge/tools-84-brightgreen.svg)](docs/use/tool-catalogue.md)
[![CI](https://github.com/woson-L/cst-studio-suite-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/woson-L/cst-studio-suite-mcp/actions/workflows/ci.yml)

An MCP server that drives **CST Studio Suite 2026** through CST's own automation API
(`cst.interface`, `cst.results`): modelling, materials, ports, boundaries, mesh, solver
selection, frequency range, monitors, solver runs, result reading and evidence export.

**84 tools · 14 categories · stdio transport · no network access.**

New here? **[Install](docs/start/install.md)** → **[Quick start](docs/use/quickstart.md)**.

---

## Origin

This server is a **refactor** of the CST MCP inside
[`Cai-aa/CAE-Agent-Hub`](https://github.com/Cai-aa/CAE-Agent-Hub) (`MCP/CST/`). That
project is MIT-licensed and its copyright notice is retained in [`LICENSE`](LICENSE).

| | Upstream | Here |
| --- | --- | --- |
| Tools | 51, in one 623-line `mcp_server.py` | **84 across 14 categories**, in a `cst_mcp/` package |
| Vendored runtime CLI | 824 files | none — a built-in command registry |
| Offline checks, CI | none covering this component | 9 gates on every push, Python 3.10 and 3.12 |
| Documentation, skills | one README; skills at the hub root | 17 documents, 2 bundled skills |

Added here: guard rails that refuse a history block CST would hang on, mesh sizing derived
from the smallest feature, project overwrite that does not strand a `Result/` directory,
and a port verdict instead of raw numbers.
**Full comparison: [Differences from upstream](docs/reference/differences-from-upstream.md).**

---

## Why this exists

A model with generic CST knowledge produces automation that *looks* right and fails in
specific, quiet ways. Every trap below was measured on CST 2026.2; the raw messages are
recorded in [`tests/evidence/known_failures.md`](tests/evidence/known_failures.md).

| Trap | What it looks like |
| --- | --- |
| **Evanescent port mode** | A waveguide port on a 1.6 mm microstrip cross-section had a **51.9 GHz cutoff** and a **6.2 kΩ** wave impedance at 2.4 GHz. S-parameters were referenced to 7623 Ω instead of 50 Ω and S11 was a flat **−0.6 dB** line — easy to mistake for an antenna. The solver had reported success. |
| **`Rebuild` inside a structure macro** | CST refuses it, and in testing the Design Environment was left **permanently unresponsive** — every later call hung. |
| **Library material + parameter change** | A library-loaded material does not survive save/reopen, so the next rebuild fails at the solid that uses it. A parameter sweep over such a project fails on **every** case. |
| **Overwriting a project by deleting the `.cst`** | A CST project is the file *plus* a companion directory holding `Model/` and `Result/`. Deleting only the file leaves the directory, and CST answers `The project directory … already exists and is non-empty`. Interactively that is the "delete the previous results?" prompt. |
| **Ports in a local coordinate system** | Endpoint coordinates are read as global `xyz`, so a `uvw` port silently lands somewhere else. |

The server turns those findings into guards, defaults and refusal messages, so the mistake
fails **loudly at the tool call** instead of quietly in the results.

## What it does

| Category | Tools | Covers |
| --- | --- | --- |
| `session` | 14 | health, detect, connect, project create/open/save/close, messages, raw VBA, history blocks, release |
| `parameters` | 4 | read, create, change, delete design parameters |
| `geometry` | 14 | brick, cylinder, sphere, cone, torus, elliptical cylinder, bond wire, boolean, transform, extrude, component |
| `material` | 3 | create, assign, load from library |
| `port` | 3 | discrete port, waveguide port, list ports |
| `solver` | 11 | solver choice, frequency range, FD/TD/eigenmode configuration, boundary, symmetry, background, run |
| `mesh` | 2 | mesh type and density, including `smallest_feature_mm` |
| `monitor` | 2 | add and list field monitors |
| `results` | 2 | result tree, read a 1D item |
| `verify` | 5 | S11, reference impedance, port info with verdict, energy budget, model audit |
| `export` | 3 | Touchstone, ASCII, summary JSON |
| `sweep` | 2 | parameter sweep: preview the case count, then run |
| `runtime` | 16 | built-in command bridge and typed wrapper generation |
| `meta` | 3 | list tools, full manifest, dynamic dispatch |

The full surface, with parameters and examples, is in
[`docs/mcp_tools.json`](docs/mcp_tools.json) — machine-readable, so another agent can read
it directly.

## Requirements

| | |
| --- | --- |
| **CST Studio Suite 2026** | Commercial software. **Not distributed here** — obtain and license it separately. Verified against the 2026.2 build. |
| **Operating system** | Windows. CST's automation API is Windows-only. |
| **Python** | 3.10 or newer, able to `import mcp`. The Python bundled with CST works. |
| **Network** | Not required. Configuration is read from a local `.env` file. |

## Quick start

```bash
# 1. find CST on this machine and write .env for you
python check_install.py --fix

# 2. verify: Python, packages, .env, the tool registry, and a real MCP handshake
python check_install.py

# 3. point your MCP client at it
#    command: python
#    args:    ["<path to>\\mcp_server.py"]
#    cwd:     <path to this folder>

# 4. first call
#    cst_health_check_tool  {}
```

`check_install.py` exits `0` when ready, `1` on warnings, `2` on problems. The full
walkthrough — including what to do on a machine with no internet access — is in
[Installation](docs/start/install.md).

## What a session looks like

A complete worked run against live CST: build a model, configure the solver, solve, read
the result and export evidence — **30 tool calls, 0 failures**. Condensed:

```
cst_connect_tool                {"launch_if_needed": true}
cst_new_project_tool            {"project_type": "mws", "path": "…\\123.cst"}
cst_define_parameters_tool      {"parameters": {"L": 50, "gap": 2, "tsheet": 5}}
cst_create_brick_tool           {"component": "parts", "name": "box", "xrange": ["-L/2","L/2"], …}
cst_add_discrete_port_tool      {"port_number": 1, "point1": [0,0,"-gap"], "point2": [0,0,"0"], "impedance": 50.0}
cst_set_solver_tool             {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool    {"fmin": 0, "fmax": 100, "unit": "MHz"}
cst_set_mesh_tool               {"mesh_type": "Tetrahedral", "steps_per_wavelength": 8}
cst_save_project_tool           {"path": "…\\123.cst", "overwrite": true}
cst_run_solver_tool             {}
cst_read_s11_tool               {"target_frequency": 100}
cst_read_reference_impedance_tool {}
cst_export_touchstone_tool      {"filename": "…\\evidence\\123_s11", "impedance": 50.0}
```

The per-call record is in
[`tests/evidence/mcp_calls_123_report.md`](tests/evidence/mcp_calls_123_report.md).

## Documentation

Everything lives in [`docs/`](docs/), indexed in **[docs/README.md](docs/README.md)**.

| I want to | Read |
| --- | --- |
| Install on this machine | [Installation](docs/start/install.md) |
| Hand the install to another AI | [Install via another agent](docs/start/install-via-agent.md) |
| Update an existing installation | [Upgrading](docs/start/upgrade.md) |
| Start using the server | [Quick start](docs/use/quickstart.md) |
| See what a session looks like | [Usage](docs/use/usage.md) |
| Browse the tools | [Tool catalogue](docs/use/tool-catalogue.md) |
| Know the rules that keep results trustworthy | [Rules](docs/use/rules.md) |
| Know what CST 2026.2 does not expose | [CST 2026.2 limits](docs/use/cst-2026-limits.md) |
| Know the server's own limits | [Known limits](docs/use/known-limits.md) |
| Add a tool or a tool family | [Extending](docs/extend/overview.md) |
| Understand the repository layout | [Layout](docs/dev/layout.md) |
| Run the verification | [Verification](docs/dev/verification.md) |

Documentation follows progressive disclosure: each file is short and links to its
siblings. Read only the file that answers the current question.

## Verification

The offline checks need no CST installation and run in CI:

```bash
python check_install.py --quick
python tests/smoke_registry.py
python tests/check_mcp_compliance.py
python tests/check_self_description.py
python tests/check_skill_tool_refs.py
python tests/check_skill_layout.py
python tests/check_docs_consistency.py
python tests/test_audit_regressions.py
python tests/test_port_info_verdict.py
python tests/test_save_overwrite.py
```

The live runners need a licensed CST and a spare ~2 GB of RAM; they are run by hand, and
their results are recorded in [Verification](docs/dev/verification.md).

## Repository layout

```
├── mcp_server.py         MCP entry point, registry bootstrap, manifest builder
├── check_install.py      installation acceptance check
├── cst_mcp/              server implementation, one module per tool category
├── skills/               two bundled agent skills
├── docs/                 documentation, grouped index in docs/README.md
├── tests/                offline gates, live runners, curated evidence
└── .env.example          configuration template (`.env` is never committed)
```

Full tree with per-file notes: [Layout](docs/dev/layout.md).

## Contributing

Read [`AGENTS.md`](AGENTS.md) first — it defines the documentation-sync requirement, and
it is enforced by the checks above. Then see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Two ground rules, because the project drives a commercial simulator:

1. **A change includes its documentation.** If your change makes a document inaccurate,
   that document is corrected in the same pull request.
2. **Do not document behaviour you have not verified.** Read the implementation, or
   measure it against CST. Untested claims are removed, not merged.

## Security

The server runs locally, speaks MCP over stdio and makes no network requests. Report
vulnerabilities privately — see [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Thompson Labs.

This project **does not distribute CST Studio Suite**, which is commercial software and
must be obtained and licensed separately. It calls the automation API that CST ships.
