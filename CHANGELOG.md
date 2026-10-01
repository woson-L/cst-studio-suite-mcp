# Changelog

Notable changes to `cst-studio-suite-mcp`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Overwriting an existing project no longer needs a confirmation.** `cst_save_project_tool`
  with `overwrite: true` used to delete only the `.cst` file and then call CST's
  `save(path)`. A CST project is the `.cst` file *plus* a companion directory holding
  `Model/` and `Result/`, so the directory survived and CST refused with
  `The project directory <dir> already exists and is non-empty. It would be overwritten.`
  — interactively that is the "delete the previous results?" prompt, which stalls an
  unattended run. The tool now closes whatever project occupies that path and lets CST's
  own `allow_overwrite` replace the file and the directory together. The server never
  deletes project files itself. Regression: `tests/test_save_overwrite.py`.
- The bundled skill and the limits documents claimed CST "has no overwrite flag". It does
  (`Project.save(path, include_results, allow_overwrite)`); the claim is corrected.

## [2.0.0]

### Changed

- **Breaking:** the package was restructured into `cst_mcp/` with one module per tool
  category, and the tool surface was rebuilt around it. Installations of the previous
  package should be removed before installing this one — the console script name is
  unchanged, but the modules behind it are not.
- Documentation moved to `docs/` with a grouped index; `AGENTS.md` records the
  documentation-sync requirement.

### Added

- `check_install.py` — installation acceptance check (`--quick`, `--fix`,
  `--list-installs`).
- Offline gates: `tests/check_mcp_compliance.py`, `check_self_description.py`,
  `check_skill_tool_refs.py`, `check_skill_layout.py`, `check_docs_consistency.py`,
  `test_audit_regressions.py`, `test_port_info_verdict.py`.
- Live verification runners: `tests/verify_live.py`, `verify_fixes_live.py`,
  `verify_task_123.py`, `run_123_task.py`.
- Two bundled agent skills: `cst-studio-suite-mcp` and `cst2026-simulation-execution`.

[Unreleased]: https://github.com/woson-L/cst-studio-suite-mcp/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/woson-L/cst-studio-suite-mcp/releases/tag/v2.0.0
