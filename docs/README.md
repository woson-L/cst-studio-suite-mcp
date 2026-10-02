# Documentation index

> Back to the [project README](../README.md)

Documentation is grouped by task. Every file is deliberately short; related files are
linked at the end of each one.

## start/ — install and upgrade

| Document | Contents |
| --- | --- |
| [install.md](start/install.md) | Step-by-step installation on a target machine |
| [install-via-agent.md](start/install-via-agent.md) | Bootstrap prompt for handing the install to another AI |
| [upgrade.md](start/upgrade.md) | Upgrading over an existing installation |

## use/ — using the server

| Document | Contents |
| --- | --- |
| [quickstart.md](use/quickstart.md) | First run and first tool call |
| [usage.md](use/usage.md) | What a working session looks like |
| [tool-catalogue.md](use/tool-catalogue.md) | The 84 tools by category |
| [rules.md](use/rules.md) | Rules that keep results trustworthy |
| [cst-2026-limits.md](use/cst-2026-limits.md) | Capabilities CST 2026.2 does not expose |
| [known-limits.md](use/known-limits.md) | Limits of this MCP server |

## extend/ — adding capability

| Document | Contents |
| --- | --- |
| [overview.md](extend/overview.md) | How registration works, adding a tool, testing |
| [add-a-tool-family.md](extend/add-a-tool-family.md) | Adding a whole command family, with a worked example |

## dev/ — developing and verifying

| Document | Contents |
| --- | --- |
| [layout.md](dev/layout.md) | Repository layout |
| [skills.md](dev/skills.md) | The bundled agent skills |
| [verification.md](dev/verification.md) | Verification runs and evidence |

## reference/ — records

| Document | Contents |
| --- | --- |
| [differences-from-upstream.md](reference/differences-from-upstream.md) | What this package changes relative to the upstream CST MCP |
| [documentation-restructure-plan.md](reference/documentation-restructure-plan.md) | How this documentation structure was derived |
| [skill-merge-evaluation.md](reference/skill-merge-evaluation.md) | Evaluation of merging two bundled skills (not executed) |

## Machine-readable

| File | Contents |
| --- | --- |
| [mcp_tools.json](mcp_tools.json) | Every tool with parameters, JSON schema, examples and notes |

## Repository root

These live at the root because GitHub surfaces them by convention rather than because
they are project documentation:

| File | Contents |
| --- | --- |
| [README.md](../README.md) | Project front page and documentation index |
| [AGENTS.md](../AGENTS.md) | Mandatory rules for changes made by an AI agent |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | What to run before opening a pull request |
| [SECURITY.md](../SECURITY.md) | How to report a vulnerability, and what is in scope |
| [CHANGELOG.md](../CHANGELOG.md) | Notable changes per version |

---

## Documentation rules

1. Project documentation lives under `docs/`. The exceptions are the root `README.md`
   and the four repository-convention files listed above.
2. Documentation follows progressive disclosure. Keep each file short; link to related
   files instead of duplicating content.
3. The root `README.md` carries a summary and a directory. Details belong in the linked file.
4. Feature changes must update the related documentation in the same change. The mapping is
   in [AGENTS.md](../AGENTS.md).
5. During discussion, no documentation work is required. Once a plan is approved and
   implementation starts, documentation is updated as part of the change.


> **`skills/` is exempt from rule 1.** A skill's `SKILL.md` and `references/` must stay at
> `skills/<name>/` because the skill discovery mechanism requires that location. Those files
> are product content, not project documentation. See [dev/skills.md](dev/skills.md).

---

## Related documents

* [Project README](../README.md) — the front page and summary this index expands
* [AGENTS.md](../AGENTS.md) — the mandatory rules, including the change-to-document mapping this index follows
* [CONTRIBUTING.md](../CONTRIBUTING.md) — what to run before opening a pull request
