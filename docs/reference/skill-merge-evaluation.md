# Skill merge evaluation: cst-studio-suite-mcp + cst2026-simulation-execution

> **Historical record.** Written while three skills were present. The package now ships
> **two** — see [Skill set](../dev/skills.md) for the current state. The findings,
> recommendation and conclusion below are preserved exactly as written and have not
> been revisited.

> Status: **evaluation complete, awaiting approval to execute**. No files were changed.
> Subjects: the two skills under `C:\CST-MCP\skills\`
> Method: read both SKILL.md files in full + the section structure of all 7 references files + line-by-line duplicate detection

---

## 1. Conclusion

**The merge is possible. Merging is recommended, under the name `cst-em-execution`.**

But what should be merged is the **entry layer (SKILL.md)**; the 11 files under `references/` **stay independent and are only grouped**.
The reasoning is in section 3: merging references would create 15–30 KB monolithic files, which conflicts with the progressive-disclosure principle;
merging SKILL.md, by contrast, removes exactly the biggest problem today.

---

## 2. Evidence supporting the merge

### 2.1 The core rules exist in three places (the decisive problem)

Each of the two skills' SKILL.md files has a "non-negotiable rules" subsection, and **all 7 items overlap item by item**:

| Rule | cst-studio-suite-mcp | cst2026-simulation-execution |
| --- | --- | --- |
| Parameters may only go through `cst_set_parameters_tool` | SKILL.md rule 1 | SKILL.md non-negotiable rule 1 |
| Save first, set the frequency range first | SKILL.md rule 2 | SKILL.md mandatory order subsection |
| A successful solve ≠ a correct result | SKILL.md rule 3 | SKILL.md four checks |
| Values come from exported files; `Abs(E)` is not gain | SKILL.md rule 4 | SKILL.md non-negotiable rule 4 |
| Must end with `cst_quit_tool`; about 700 MB per project | SKILL.md rule 5 | SKILL.md non-negotiable rule 5 |
| CST 2026.2 has no separate mesh step | SKILL.md "two traps" | SKILL.md non-negotiable rule 2 |
| `smallest_feature_mm` and preprocessing failures | SKILL.md "two traps" | SKILL.md non-negotiable rule 3 |

**The same set of rules currently exists in three copies**:

1. `cst-studio-suite-mcp/SKILL.md` — condensed version (a list of rules)
2. `cst-studio-suite-mcp/references/guard-rails-and-limits.md` — full version (Rule 1–5, each its own subsection)
3. `cst2026-simulation-execution/SKILL.md` — condensed version (listed out item by item again)

Of these, 1 and 3 are duplication at the same level. **This list is the safety boundary of this project** — the consequence of
mistake 1 (writing `StoreParameter` into a history block) is a permanently unresponsive Design Environment.
Once the two copies diverge, which one you happened to read determines the behaviour, and that is an unacceptable maintenance risk.

### 2.2 The two skills are always needed together in practice

Judging by their own stated positioning:

- Loading only the mcp skill: you know the call order, but not which enum values are legal or whether a result can be trusted
- Loading only the execution skill: you know the legal values and the verification rules, but not the categories and order of the 84 tools

A planning-only task needs only the former; but as soon as you move into actual execution, both are needed.
The current design leaves the burden of judging "whether to load the second one" to the caller, while the basis for that judgement is itself written in the first skill.

### 2.3 The explanation of the split axis is itself a maintenance burden

`cst-studio-suite-mcp/SKILL.md` spends a whole section (lines 24–35) explaining the division of labour between the two skills
and gives a mnemonic for deciding. After the merge that section simply disappears, with no loss of information.

---

## 3. Objections to merging, and why they do not hold

### 3.1 Size (the only substantive objection)

| | Files | Bytes |
| --- | --- | --- |
| cst-studio-suite-mcp | 10 | 55,692 |
| cst2026-simulation-execution | 7 | 31,078 |
| Total | 17 | 86,770 |

If the merge produced a single document, it would be an 87 KB monolith — in direct conflict with the progressive-disclosure principle.

**But merging does not require merging the bodies.** The existing structure is already SKILL.md + references/:

- After the merge, SKILL.md ≈ 10–12 KB (serving as an index to the 11 references files plus a summary of the rules)
- The 11 references files stay independent and are read on demand

Control case: the current `cst-studio-suite-mcp/SKILL.md` is 8.5 KB and indexes 7 files, and it works fine.
What the merge adds is two sections, "legal enum value index" and "verification check index", about 2–3 KB.

### 3.2 "Every skill must be self-contained"

This is the legitimate reason for duplicating the rules today: when only one of them is loaded, the safety rules still need to be visible.

**After the merge this reason disappears on its own** — there is only one skill, so the case of "loading only one of them" does not exist.

---

## 4. The actual state of references (the basis for not merging the bodies)

Line-by-line duplicate detection on the two verification-type files:

```
cst-studio-suite-mcp/references/result-validation.md
  vs
cst2026-simulation-execution/references/solve-verify-evidence.md
  → long lines that are entirely identical, line by line: 0 lines
```

The two are adjacent in topic but their content does not overlap:

| File | Content |
| --- | --- |
| `result-validation.md` | Sectioned by physical quantity: S-parameters / VSWR / far field / near field and currents / eigenmodes / parameter sweeps; report status values |
| `solve-verify-evidence.md` | Sectioned by process: solve → what counts as "simulated" → verification set → numerical handling → evidence and reproducibility → diagnostic table |

**Conclusion: the references files are complementary to one another and should be kept as independent files.** Merging them would not eliminate duplication;
it would only create monolithic documents.

---

## 5. Merge plan

### 5.1 Target structure

```
skills/cst-em-execution/
├── SKILL.md                          ← the single entry point after the merge (about 10–12 KB)
└── references/
    ├── workflow.md                   ← formerly mcp/refs (the five modes and the standard sequence)
    ├── parameter-policy.md           ← formerly mcp/refs
    ├── templates.md                  ← formerly mcp/refs
    ├── tool-catalogue-and-order.md   ← formerly mcp/refs (15,890 B, kept independent)
    ├── result-validation.md          ← formerly mcp/refs
    ├── guard-rails-and-limits.md     ← formerly mcp/refs (full Rule 1–5, becomes the single source of the rules)
    ├── extending-and-conventions.md  ← formerly mcp/refs
    ├── solver-and-band.md            ← formerly execution/refs
    ├── ports-boundaries-mesh.md      ← formerly execution/refs
    ├── solve-verify-evidence.md      ← formerly execution/refs
    └── worked-example.md             ← formerly execution/refs
```

**All 11 files keep their original names**, neither merged nor rewritten. Only their host directory changes.

### 5.2 Sections of SKILL.md after the merge

| Section | Source | Handling |
| --- | --- | --- |
| frontmatter `name` | — | change to `cst-em-execution` |
| frontmatter `description` | both merged | cover both layers, "orchestration + execution correctness"; keep the trigger conditions |
| Step 0 request classification (five modes) | mcp | keep |
| Input policy (ask once, take defaults for the rest) | mcp | keep |
| Operating rules | mcp | keep |
| **Non-negotiable rules (7)** | **both** | **merge into one copy**, each item pointing to `guard-rails-and-limits.md` |
| Four quotable checks | execution | keep |
| Mandatory order | execution | keep |
| Verification status values | mcp | keep |
| Reference file index | both | merge into one table (11 rows) |
| Where to look when something fails | mcp | keep |
| ~~This skill vs cst2026-simulation-execution~~ | mcp | **delete** (that division of labour no longer exists) |

### 5.3 Draft description after the merge

```
Plan, run and validate CST Studio Suite 2026 simulations through the CST MCP server.
Use when an agent must operate CST: classify the request (plan only, new project,
existing project, parameter study, optimization), resolve inputs and defaults, pick
a template, then model, assign materials, place ports, set boundaries / mesh /
solver / frequency range / monitors, solve, and prove the result is physically
meaningful. Carries the verified CST 2026.2 command strings and enum values, the
port and mesh defects that silently produce meaningless S-parameters, the evidence
rules that decide whether a number is quotable, and the call order for all 84 tools.
```

---

## 6. Scope of impact

| Affected item | Impact | Handling |
| --- | --- | --- |
| Agent sessions that load these two skills by name | the names stop working | must be remounted; see the migration steps |
| `C:\CST-MCP\README.md` § Skill set | describes two skills | change to one |
| Cross-references inside the various SKILL.md files | point at each other | change to point at `references/` |
| The division-of-labour explanation at lines 24–35 of `cst-studio-suite-mcp/SKILL.md` | obsolete | delete |
| References in `tests/evidence/` | to be confirmed | grep needed before migration |
| The skill check in `check_install.py` | to be confirmed | confirm before migration whether it is hard-coded by name |

**Two items not yet verified**: whether `tests/evidence/` and `check_install.py` reference these two skills by name.
A grep confirmation is mandatory before migration; if they are hard-coded, they must be changed in step.

---

## 7. Migration steps

Every step has a verification point, and a failure can be stopped or rolled back.

| # | Action | Verification |
| --- | --- | --- |
| 0 | Back up the whole `C:\CST-MCP\skills\` directory | record the file count and total bytes |
| 1 | grep the whole package and list every place that references these two skill names | the list matches expectations |
| 2 | Create `skills/cst-em-execution/` | the directory exists |
| 3 | Copy all 11 files from the two skills' `references/` into the new directory | 11 files, byte counts identical to the sources |
| 4 | Write the new SKILL.md per section 5.2 | all sections present; the 7 rules appear only once |
| 5 | Update `README.md` § Skill set | it describes only one skill |
| 6 | Update every reference in the list from step 1 | grep returns zero |
| 7 | Delete the two old skill directories | the directories do not exist |
| 8 | Actually run one plan-only task and one solve task | both modes can trigger the new skill |

**Rollback**: before step 7, deleting the new directory restores everything completely; after step 7, restore from the step 0 backup.

---

## 8. Risks

| Risk | Level | Description | Mitigation |
| --- | --- | --- | --- |
| A longer description changes trigger decisions | medium | the merged description covers two layers and may change matching behaviour | measure triggering on both kinds of task after migration (step 8) |
| Undiscovered hard-coded references | medium | if the step 1 grep misses any, they only surface at runtime | besides grep, run `check_install.py` once |
| Accidentally deleting a rule during the merge | high | the rules are the safety boundary of this project | accept it by checking item by item against the table in section 2.1 |
| The source of the rules is still not unique in a single file | low | after the merge the condensed version and the full `guard-rails-and-limits.md` still coexist | annotate each item of the condensed version with "see references/guard-rails-and-limits.md", and treat the full version as the sole authority |


---

## Appendix A: Confirmed results for the reference surface (measured 2026-09-30)

The original section 6 listed `tests/evidence` and `check_install.py` as "not yet verified". They have now been confirmed by a whole-package grep,
and **the reference surface is far larger than estimated**, with most of it sitting in executable code.

### A.1 Hard-coded references in executable code

| File | Lines | Nature |
| --- | --- | --- |
| `check_install.py` | 258–263 | the check list enumerates both skills' SKILL.md / metadata.json / agents/openai.yaml |
| `check_install.py` | 271–272 | expected references counts: `("cst-studio-suite-mcp", 7)`, `("cst2026-simulation-execution", 4)` |
| `mcp_server.py` | 61, 126 | references inside the MCP server |
| `pyproject.toml` | 6, 24 | packaging and metadata |
| `tests/check_skill_layout.py` | 31 | skill directory structure check |
| `tests/check_skill_tool_refs.py` | 46, 47 | check of tool references inside skills |
| `tests/check_docs_consistency.py` | 25, 26 | documentation consistency check |
| `tests/check_self_description.py` | 119 | self-description check |
| `tests/verify_task_123.py` | 12, 13 | task verification script |
| `tests/mcp_compliance.json` | 4, 8, 64 | compliance record |
| `tests/evidence/mcp_compliance.json` | 4, 8, 64 | compliance record (archived copy) |

### A.2 References in documentation

| File | Count |
| --- | --- |
| `README.md` | 10 places (12, 169, 170, 226, 266, 267, 297, 298, 300) |
| `INSTALL_AGENT.md` | 14 places |
| `安装说明指引.md` | 6 places |
| `tests/evidence/known_failures.md` | 1 place (358) |
| `docs/mcp_tools.json` | 1 place (line 2, the machine-readable tool catalogue) |

### A.3 Conclusion

**`check_install.py` uses `record(OK if ... else WARN)`; absence only warns, it does not fail.**
So the merge will not hard-stop an installation, but it will produce warnings and must be changed in step, otherwise the install check loses its meaning.

**Before deleting the old skills, every item in A.1 and A.2 must be updated first.** Until then the old and new skills coexist,
which does not affect any existing functionality.

---

## Appendix B: Work already completed (2026-09-30)

| Step | Status | Notes |
| --- | --- | --- |
| 0 Backup | ✅ | `C:\CST-MCP-backup\skills-pre-merge-20260930_233935\` (17 files / 86,770 bytes) |
| 1 grep reference points | ✅ | see Appendix A |
| 2 Create directory | ✅ | `skills/cst-em-execution/` |
| 3 Copy references | ✅ | 11 files, byte counts checked one by one against the sources |
| 4 Write the new SKILL.md | ✅ | 10,202 bytes; the 7 rules appear only once; all 11 references files are named, none missing, none extra |
| 4b metadata.json + agents/openai.yaml | ✅ | newly created (every skill in the source package has these two companion files; the original evaluation missed them) |
| 5 Update README § Skill set | ⬜ | to do |
| 6 Update all references from Appendix A | ⬜ | **blocks the deletion action** |
| 7 Delete the two old skills | ⬜ | requires step 6 to be done first |
| 8 Measure triggering | ⬜ | one plan-only task and one solve task |

**Current state: three skills coexist, the new skill is fully usable, and the old skills are unaffected.** Deleting
`skills/cst-em-execution/` at any moment returns to the pre-merge state.

---

## Related documents

* [Skill set](../dev/skills.md) — the skills as they stand today, to compare against this evaluation
* [Documentation restructure plan](documentation-restructure-plan.md) — the other record that shaped this documentation set
* [Verification](../dev/verification.md) — `check_install.py`, which Appendix A found still names both skills
* [Failures hit during development](../../tests/evidence/known_failures.md) — the other file Appendix A flags as referencing them
* [Documentation index](../README.md) — where this record is listed and how the set is grouped
