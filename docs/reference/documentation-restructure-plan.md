# CST-MCP documentation restructure plan

> Status: **plan pending confirmation**. No files have been moved.
> Basis: the five documentation rules given by the user (docs kept in one place, progressive
> disclosure, root README as index, AGENTS.md mandatory sync, two-phase split of discussion and execution).

---

## 1. Current-state inventory

| File | Language | Bytes | Topic |
| --- | --- | --- | --- |
| `README.md` | EN | 20,575 | overview / quick start / tool catalogue / rules / structure / skill set / verification / installing over an existing installation / limits |
| `INSTALL_AGENT.md` | CN | 17,445 | handing the installation to another AI: prompt, manual preparation, blockers, file purposes |
| `安装说明指引.md` | CN | 27,321 | manual installation: pre-checks, placing files, writing `.env` |
| `docs/ADDING-A-TOOL-FAMILY.md` | CN | 15,614 | adding a tool family: mechanism, registration, pyproject, examples, five pitfalls, acceptance checklist |
| `docs/EXTENDING.md` | EN | 13,210 | extension mechanism, adding tools, rules, tests, tool families, parameter-sweep example |

**Overlaps found**:

1. `ADDING-A-TOOL-FAMILY.md` (CN) and `EXTENDING.md` (EN) cover **the same topic**, and each has a complete example of a parameter-sweep tool family.
2. "Installing over an existing installation" in `README.md` overlaps with the two installation documents.
3. `README.md` serves as both index and body text at 20 KB, which conflicts with its stated role of "root README as index".

**Structural gaps**:

- The root README is not an index, it is a collection of body text
- `docs/` holds only two files, and they are the same topic in two languages
- No `AGENTS.md`

---

## 2. A decision that must be made first: documentation language

The current state is mixed Chinese and English:

- README and EXTENDING are in English
- the installation guide, INSTALL_AGENT and ADDING-A-TOOL-FAMILY are in Chinese

The restructure will **amplify** this problem: when merging `EXTENDING.md` and `ADDING-A-TOOL-FAMILY.md`,
one language must be chosen, otherwise the merged file is still mixed.

Three possible directions:

| Direction | Approach | Cost |
| --- | --- | --- |
| **A. All English** | translate the Chinese documents into English | consistent with the upstream DSH ecosystem; the largest translation workload |
| **B. All Chinese** | translate the English documents into Chinese | aimed at Chinese-speaking users; inconsistent with the English skills of `cst-studio-suite-mcp` |
| **C. Two layers** | provide a `.md` and a `.zh-CN.md` for every document | no translation loss; the number of files doubles, and the two copies must be kept in sync |

**C is recommended, but only for user-facing documents** (installation, quick start, limits);
developer-facing documents (extension, build) are advised to be English-only, to avoid maintaining two copies long term.

Until the direction is settled, merging `EXTENDING` and `ADDING-A-TOOL-FAMILY` cannot proceed.

---

## 3. Target structure

```
C:\CST-MCP\
├── README.md                     ← index: one-line positioning + grouped contents table (target ≤ 120 lines)
├── AGENTS.md                     ← new: mandatory documentation-sync rules
└── docs/
    ├── README.md                 ← grouped index (new)
    │
    ├── start/                    ← get it installed
    │   ├── install.md            ← manual installation (formerly 安装说明指引.md)
    │   ├── install-via-agent.md  ← hand the installation to an AI (formerly INSTALL_AGENT.md)
    │   ├── env.md                ← the .env configuration items (split out of the installation guide)
    │   └── preflight.md          ← capabilities CST 2026.2 does not have, pre-checks
    │
    ├── use/                      ← get it used
    │   ├── overview.md           ← quick start, usage examples (the corresponding README sections)
    │   ├── rules.md              ← result-trust rules
    │   └── limits.md             ← known limitations
    │
    ├── extend/                   ← extension
    │   ├── overview.md           ← registration mechanism (originally EXTENDING §1)
    │   ├── add-a-tool.md         ← adding a single tool (originally EXTENDING §2–5)
    │   ├── add-a-tool-family.md  ← adding a tool family (originally ADDING-A-TOOL-FAMILY)
    │   └── checklist.md          ← acceptance checklist
    │
    ├── dev/                      ← development and operations
    │   ├── layout.md             ← directory structure (originally README "Layout")
    │   ├── verification.md       ← verification (originally README "Verification")
    │   └── skills.md             ← description of the skill set
    │
    └── reference/
        └── skill-merge-evaluation.md   ← already in this directory
```

### The exception for the `skills/` directory

The rule "documents are stored in the docs directory" **does not apply to `skills/`**.

The location of `SKILL.md` and `references/` is fixed by the skill discovery mechanism (`<root>/<name>/SKILL.md`),
they are not ordinary documents. Moving them into `docs/` would break the skills.

Therefore: **the files under `skills/` are this project's "product content", not "project documentation"**, and stay unchanged.
`docs/dev/skills.md` only explains what this set of skills is and how it is loaded.

---

## 4. File-by-file disposition

| Original file | Destination | Handling |
| --- | --- | --- |
| `README.md` | split into `README.md` + `docs/use/*` + `docs/dev/*` | keep the index part, move the body text out by topic |
| `INSTALL_AGENT.md` | `docs/start/install-via-agent.md` | move verbatim; fix relative paths |
| `安装说明指引.md` | `docs/start/install.md` + `docs/start/env.md` | split into "installation steps" and ".env configuration" |
| `docs/EXTENDING.md` | `docs/extend/overview.md` + `add-a-tool.md` | split by section |
| `docs/ADDING-A-TOOL-FAMILY.md` | `docs/extend/add-a-tool-family.md` | move verbatim |
| (the duplicated example in the two extension documents) | merged into `add-a-tool-family.md` | keep the one with the fuller information, turn the other into a link |

**The migration is mainly verbatim relocation**; rewriting is limited to: language unification (pending decision), relative-link fixes,
and changing cross-references from "see section N" into file links.

---

## 5. Contents of AGENTS.md

Following the rule structure already validated by dsh-antenna-optimizer, adjusted for this project:

1. **Changing behaviour = changing code + changing documentation (mandatory)**, with a "change → document" mapping table
2. **Documentation writing conventions**: progressive disclosure, index on top, related documents at the end, relative links rather than section numbers across documents
3. **Periodic manual spot checks (mandatory)**: rules do get missed, so spot-check once per release cycle; what to check and what to record
4. **Way of working**: no documentation changes during the discussion phase; once the plan is confirmed and execution begins, the AI updates them in sync
5. **Pre-commit self-check list**
6. **Technical constraints of this project**: the location of `skills/` is fixed by convention and cannot be moved; `check_install.py` is the acceptance entry point

---

## 6. Preconditions for execution

| # | Precondition | Status |
| --- | --- | --- |
| 1 | settle the documentation language direction (section 2) | ⬜ pending |
| 2 | confirm the language of the merged `ADDING-A-TOOL-FAMILY` and `EXTENDING` | ⬜ depends on 1 |
| 3 | grep the whole package to confirm nothing references the old document paths by hard-coded name | ⬜ to do |
| 4 | back up the whole of `C:\CST-MCP\docs\` and the three root-level `.md` files | ⬜ to do |
| 5 | confirm `skills/` stays in place (the exception clause in section 3) | ⬜ to confirm |

**Item 1 is the only hard blocker**: while the language direction is undecided, the "merge the two extension documents" of section 4 cannot be carried out,
and that is the only part of this restructure that involves rewriting.

---

## 7. Relationship to the skill merge

The two things are **independent of each other** and can be advanced separately:

| | Documentation restructure | Skill merge |
| --- | --- | --- |
| Subject | `docs/` and the root-level `.md` files | the two skills under `skills/` |
| Status | language direction pending | evaluation complete, awaiting approval |
| Intersection | the description in `docs/dev/skills.md` must match the merge result | that document must be updated after the merge |

**Suggested order**: do the skill merge first (the conclusion is already clear and the scope of impact has been listed), then restructure the documents —
so that `docs/dev/skills.md` only has to be written once.
