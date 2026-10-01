# Contributing

Thanks for considering a contribution. This project drives a commercial simulator through
its automation API, so the bar for a change is *evidence*, not enthusiasm: a claim about
CST behaviour is only accepted when it was measured on a real installation.

## Before you start

Read [`AGENTS.md`](AGENTS.md). It is short and it is mandatory. Two rules matter most:

1. **A change includes its documentation.** If your change makes a statement in any
   document inaccurate, that document is corrected in the same pull request. The
   change → document mapping is in `AGENTS.md`.
2. **Do not document behaviour you have not verified.** Read the implementation, or
   measure it against CST. "It should work like this" is not a source.

## What is easy to contribute

| Kind of change | Notes |
| --- | --- |
| A new report or evidence file | Add it under `docs/` and register it in `docs/README.md` |
| A correction to a limit or a verified value | Quote the CST build and the exact message you measured |
| A new offline regression test | These run without CST, so they belong to `tests/check_*.py` / `test_*.py` |
| Documentation fixes | Typos, broken links, unclear steps — always welcome |

## What needs discussion first

Open an issue before writing code for any of these:

- a new tool or tool family (see [`docs/extend/overview.md`](docs/extend/overview.md))
- changing an existing tool's parameters or return shape
- anything that changes a bundled skill under `skills/`

## Checks to run before opening a pull request

Offline checks need no CST installation:

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

All of them must report **0 problems** and exit `0`. If your change touches the tool
surface, regenerate the manifest:

```bash
python tests/smoke_registry.py      # rewrites docs/mcp_tools.json
```

Live runners (`tests/verify_*.py`, `tests/run_123_task.py`) need a licensed CST
installation. Run them when your change touches the CST bridge, and paste the summary
into the pull request.

## Pull requests

- One concern per pull request. A fix and a refactor are two pull requests.
- Describe **what you measured**, not only what you changed. Include the CST version and
  the exact message for anything that failed before your change.
- If a document changed, say which one and why in the description.

## Scope

This repository does **not** distribute CST Studio Suite. Contributions that would
require redistributing CST files, licence keys, or vendor documentation cannot be
accepted.

## Licence

By contributing you agree that your contribution is licensed under the MIT Licence, as
described in [`LICENSE`](LICENSE).
