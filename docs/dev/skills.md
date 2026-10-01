# Skill set

> **Documentation index** › Skill set


Two skills ship with this package, split by **question** rather than by tool:

| Skill | Answers |
| --- | --- |
| `cst-studio-suite-mcp` | what to do (mode), what may be defaulted, which template, which tool in what order, what evidence the report needs |
| `cst2026-simulation-execution` | which enum values are legal, and whether the result can be believed |

`cst-studio-suite-mcp` also covers the request classification, defaults and reporting
that were previously a separate workflow skill; that skill no longer exists (a copy is
kept outside this folder as `CST-MCP-superseded/` in case a rollback is wanted).

---

## Related documents

* [Layout](layout.md) — where `skills/` sits in the repository tree
* [Skill merge evaluation](../reference/skill-merge-evaluation.md) — the analysis behind the two-skill split
* [Verification](verification.md) — the checks that keep the skill references valid
* [Extending the tool surface](../extend/overview.md) — adding a tool a skill should describe
* [Agent rules](../../AGENTS.md) — why `skills/` may not move and what a skill change must update
