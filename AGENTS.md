# AGENTS.md — working rules for this repository

> These rules apply to AI agents and to human contributors.

---

## 1. A feature change includes its documentation (mandatory)

A change is complete only when the documentation it invalidates has been updated in the
same change. Documentation is part of the change, not a follow-up.

If a change makes a statement in any document inaccurate, that document must be corrected
in the same change.

### Change → document map

| Change | Update |
| --- | --- |
| Install steps, prerequisites, `.env` keys | [`docs/start/install.md`](docs/start/install.md) |
| Upgrade procedure | [`docs/start/upgrade.md`](docs/start/upgrade.md) |
| A tool is added, removed or renamed | [`docs/use/tool-catalogue.md`](docs/use/tool-catalogue.md) + [`docs/dev/verification.md`](docs/dev/verification.md) |
| Tool parameters or return shape | [`docs/mcp_tools.json`](docs/mcp_tools.json) (regenerate) |
| A result-trust rule changes | [`docs/use/rules.md`](docs/use/rules.md) |
| A limit is discovered or lifted | [`docs/use/known-limits.md`](docs/use/known-limits.md) |
| Repository layout changes | [`docs/dev/layout.md`](docs/dev/layout.md) |
| A bundled skill changes | [`docs/dev/skills.md`](docs/dev/skills.md) |
| A new document is added | [`docs/README.md`](docs/README.md) index |
| A release is cut, or a user-visible change lands | [`CHANGELOG.md`](CHANGELOG.md) |
| What contributors must run before a pull request changes | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| The offline checks or CI workflow change | [`CONTRIBUTING.md`](CONTRIBUTING.md) + [`docs/dev/verification.md`](docs/dev/verification.md) |

---

## 2. Technical constraints

**Do not move anything under `skills/`.** The location `skills/<name>/SKILL.md` is required by
the skill discovery convention. Moving a skill into `docs/` breaks it.

**Moving a document requires updating `check_install.py`.** The installation acceptance check
names documents by path (the `for doc in (...)` list). A moved document that is not reflected
there produces a `WARN` in the install check.

**Validate with `check_install.py` and the `tests/` runners.** `check_install.py` is the
installation acceptance entry point. The `tests/check_*.py` scripts verify documentation, skill
layout and tool references — run them after any structural change.

---

## 3. Documentation conventions

* Write in English. The one exception is the README pair: [`README.md`](README.md) is the
  English front page and [`README.zh-CN.md`](README.zh-CN.md) is its Chinese translation.
  They change together, in the same commit, keeping the same section order and the same set
  of links.
* Keep each file short. If a file exceeds roughly 300 lines, split it.
* The root [`README.md`](README.md) is the index. The grouped index is
  [`docs/README.md`](docs/README.md). Every new document must appear in the grouped index.
* End every document with a list of related documents.
* Cross-document references use relative links. Do not use section numbers ("see section 4") —
  numbering drifts when files are split.
* Do not document behaviour that has not been verified. Read the implementation when unsure.

---

## 4. Rules get missed — periodic human review is mandatory

Adding a rule does not guarantee it is followed. Some changes will land without their
documentation update.
Therefore a human contributor reviews documentation at least once per release cycle:

1. Do recent feature changes have matching documentation?
2. Do any documents contradict the implementation — especially defaults, field names and
   commands?
3. Are cross-document links intact? Directory moves break links first.
4. Is every document listed in the grouped index?

When a discrepancy is found, decide which side is wrong. Documentation and implementation must
converge on the verified behaviour.
Record the review outcome in the commit message or an issue, not only in a chat log.

A practical check: after a code change, ask the agent to read the affected documents and report
what is now stated incorrectly. That produces better results than asking whether the
documentation needs updating.

---

## 5. Working agreement

* **Discussion phase** — discuss the approach. No documentation work is required, and no draft
  documents are produced.
* **Implementation phase** — once the plan is approved and implementation starts, the AI updates
  the documentation together with the code. The human verifies consistency during review.

This avoids two failure modes: writing documents that are discarded during discussion, and
leaving documentation behind during implementation.

---

## 6. Pre-commit checklist

- [ ] Change implemented
- [ ] `check_install.py` passes without new warnings
- [ ] Relevant `tests/check_*.py` runners pass
- [ ] Documents in the change map above are updated
- [ ] New documents are listed in `docs/README.md`
- [ ] Cross-document links resolve
- [ ] `docs/mcp_tools.json` regenerated if the tool surface changed
