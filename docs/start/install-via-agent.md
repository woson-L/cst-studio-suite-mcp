# Handing CST-MCP to Another AI to Install — Bootstrap Instructions

> Usage: copy the entire prompt from **Section 2** to the AI on the target computer (the local model inside the Harness).
> It depends on no context on this machine; it is self-contained. Section 3 is the part you (the human) have to do, and Section 4 is troubleshooting.

---

## 1. First, Be Clear About What the AI Is Actually Installing

This folder holds **two independent things**; they are installed differently and **must be handled separately**:

| Item | What it is | Where it goes | How you know it is installed |
|---|---|---|---|
| **MCP server** | `mcp_server.py`, which provides 84 `cst_*` tools | There is no "installation"; you only need: ①`<PYTHON>` can `import mcp`; ② `.env` is written correctly; ③ the Harness points at it | `cst_health_check_tool` returns `ready: true` |
| **Skills (2 of them)** | The `SKILL.md` files under `skills\`: **instructions written for the AI**, not code | Copy them into the Harness's **skills directory** | Both names are visible in the Harness's skill list |

**The most common failure**: configuring only the MCP and not installing the skills. The result is an AI
that has 84 tools but does not know how to use them, so it tends to try things at random, write wrong
CST method names, and treat invalid results as valid ones.

How the two skills divide the work:

| Skill | Role |
|---|---|
| `cst-studio-suite-mcp` | Tool catalogue, call order, parameter essentials, guard rails (**how to use this tool set**) |
| `cst2026-simulation-execution` | Measured enumeration values, port criteria, mesh sizes, result validity checks (**how to make sure the results are correct**) |

---

## 2. The Prompt for the AI (copy it in full)

```text
Your task: install and verify, on a certain computer, an MCP server called CST-MCP together with the
two skills that come with it, so that this Harness can drive CST Studio Suite 2026 through it.

Background and constraints:
- The target computer is **offline**; it cannot download anything from the network.
- The CST installation path and the Python interpreter path are both **unknown**; you must probe for
  them yourself, do not assume.
- `<CST-MCP>` means the real path of that folder on your machine (ask the user, or find it yourself).
- Do **not** guess CST VBA method names from memory. The method names in this package were all measured
  on CST 2026.2, so just use them as given; if the documentation says a command does not exist, then it
  really does not exist — do not look for another way to write it.
- You carry out everything yourself; stop and ask the user only when you need information or
  authorization from them (see steps 1 and 4).

Execute in order; every step has an explicit success criterion. If any step fails, resolve it before
continuing; do not skip steps.

━━━ Step 0: Locate the folder ━━━
Confirm that <CST-MCP> exists, and list its top-level contents. You should see:
  mcp_server.py, check_install.py, .env.example, README.md,
  cst_mcp\, docs\, skills\, tests\
If you cannot see these, the folder was not copied completely: **stop and tell the user**, do not continue.

━━━ Step 1: Probe the environment (you may need the user's help) ━━━
1a. Find the CST installation location. Look for these two files:
      <CST_ROOT>\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe
      <CST_ROOT>\AMD64\python_cst_libraries\cst\results.py
    Search drive by drive, for example:
      Get-ChildItem "<drive>:\Program Files" -Directory | Where-Object { $_.Name -like "*CST*" }
    Note down <CST_ROOT> and <CST_EXE>. If you cannot find them, ask the user where CST is installed.

1b. Find a usable Python (key constraint: that interpreter must be able to `import mcp`).
    Start from the most likely places and use the first one that works, recording it as <PYTHON>:
      A) The venv bundled with the old CST MCP, for example ...\cst-studio-suite\.venv\Scripts\python.exe
      B) The one bundled with CST: <CST_ROOT>\Python\python.exe
      C) The system python (where python)
    Verify each one like this:
      & "<candidate>" -c "import sys, mcp; print(sys.version); print('mcp ok')"
    Python 3.10+ is required. If they all fail and there is no network access, **stop and ask the user**;
    do not attempt a network pip install.

1c. Find two locations (needed for step 4):

    a) **The repository's CST skill directory**. In a shared skills hub the CST skills live at
       <skills-hub>\Skill\CST\, with an existing cst-simulation-workflow at the same level. Confirm the shape:
         Get-ChildItem "<skills-hub>\Skill\CST" -Recurse -File
       Each skill is one directory containing SKILL.md, metadata.json, agents\openai.yaml and
       references\*.md. Note down <skills-hub>.

    b) **The Harness's skills directory** (if it is not that hub). It varies by client; the common ones:
         DSH: <workspace or user directory>\.dsh\skills\
         Codex / Claude: a user-level or project-level skills directory
       Ask the user, or look for a "skills" setting in your own configuration.

    The two may be the same or may differ; if they differ, put the skills in both places in step 4.

Report these five items to the user for confirmation, then continue:
  <CST-MCP>, <CST_ROOT>, <CST_EXE>, <PYTHON>, <skills-hub>

━━━ Step 2: Configure .env ━━━
2a. If <CST-MCP>\.env does not exist, copy .env.example to .env.
2b. Use --fix to probe and write the CST paths automatically:
      Set-Location "<CST-MCP>"
      & "<PYTHON>" check_install.py --fix
2c. Check that these four keys in .env are all **absolute paths** and really exist:
      CST_INSTALL_ROOT=<CST_ROOT>
      CST_DESIGN_ENVIRONMENT_EXE=<CST_EXE>
      CST_MCP_WORKSPACE=<some writable directory>
      CST_MCP_EVIDENCE=<the one above>\evidence
    Note: the values must not keep < > placeholders; --fix leaves an existing WORKSPACE
    untouched, so if it is a placeholder you have to change it by hand.

Success criterion (must hold once this step is done):
      & "<PYTHON>" check_install.py --quick
  Expected tail: passed : 44  failed : 0  →  RESULT: READY
  (If .env has not been written yet you will get 30 passed / 2 warning / 3 failed; that is expected, do not panic)

━━━ Step 3: Wire it into the Harness ━━━
Add a stdio server to the Harness's MCP configuration. The DSH way is to add it at the cordis patch layer:

  - id: mcp-cst-studio-suite
    name: '@deepseek-ai/dsh-mcp-client'
    config:
      serverName: cst-studio-suite
      transport: stdio
      command: <absolute path of PYTHON>
      args:
        - <CST-MCP>\mcp_server.py
      cwd: <CST-MCP>

Other clients write the equivalent three items: command=<PYTHON>, args=<CST-MCP>\mcp_server.py, working directory=<CST-MCP>.
Note that the indentation must match sibling entries in your configuration file (DSH's YAML uses 2 spaces).
After changing it you **must restart the Harness**, otherwise the tools will not appear.

Success criterion:
      & "<PYTHON>" check_install.py
  Expected tail: passed : 58  failed : 0  →  RESULT: READY
  (This one really launches CST and performs a handshake; if it passes, the server itself is fine)

━━━ Step 4: Install the skills (the step most easily missed) ━━━
A skill is **one directory = one skill**; the directory must contain SKILL.md and usually also carries
metadata.json, agents\openai.yaml and a references\ subdirectory. **You must copy the whole directory**;
do not copy only SKILL.md — references\ holds the detail files, and without it the skill points at thin air.

In the shared skills hub, the CST skills live at:
    <skills-hub>\Skill\CST\
So the two skills in this package should go on that same level, side by side with the existing cst-simulation-workflow:

    <skills-hub>\Skill\CST\
    ├─ README.md / README.zh-CN.md     ← index, update both of these after installing
    ├─ cst-simulation-workflow\        (already there, do not touch)
    ├─ cst-studio-suite-mcp\           ← added by this package
    └─ cst2026-simulation-execution\   ← added by this package

4a. Confirm that <CST-MCP>\skills\ holds two directories:
      cst-studio-suite-mcp\           containing SKILL.md + metadata.json + agents\ + references\
      cst2026-simulation-execution\   the same structure
    First compare the two locations and copy the shape:
      Get-ChildItem "<CST-MCP>\skills" -Recurse -File
      Get-ChildItem "<skills-hub>\Skill\CST\cst-simulation-workflow" -Recurse -File
    Both sides should have the same shape (SKILL.md + metadata.json + agents\openai.yaml + references\*.md).

4b. Copy them under <skills-hub>\Skill\CST\ (**directory-level copy**):

      $hub = "<skills-hub>\Skill\CST"
      Copy-Item "<CST-MCP>\skills\cst-studio-suite-mcp"        $hub -Recurse -Force
      Copy-Item "<CST-MCP>\skills\cst2026-simulation-execution" $hub -Recurse -Force

4c. After copying, cross-check: the hashes must match and the file counts in references\ must line up.

      foreach ($n in 'cst-studio-suite-mcp','cst2026-simulation-execution') {
        (Get-FileHash "<CST-MCP>\skills\$n\SKILL.md").Hash -eq (Get-FileHash "$hub\$n\SKILL.md").Hash
        (Get-ChildItem "$hub\$n\references" -File).Count
      }
    Expected: two True values; references counts of 7 and 4 respectively.

4d. **Update the index**. <skills-hub>\Skill\CST\README.md and README.zh-CN.md each hold a skill table;
    add the two new ones to it (table columns: Skill | Purpose — use the Chinese equivalents in the Chinese versions).
    Also check that the CST row in <skills-hub>\Skill\README.md and README.zh-CN.md is still accurate.

4e. If the Harness has its own skill installation mechanism (CLI or UI), prefer it; if not, copy the directories directly.
    If the target machine uses DSH, the skills directory is usually `.dsh\skills\` under the workspace or user directory,
    so copy there (again a **directory-level copy**).

4f. Restart the Harness and confirm that these three CST skill names appear in the skill list.

Success criteria:
  - the three skill directories under <skills-hub>\Skill\CST\ have a consistent structure;
  - the skill table in README.md / README.zh-CN.md lists all three;
  - the Harness skill list shows cst-simulation-workflow, cst-studio-suite-mcp and
    cst2026-simulation-execution.

━━━ Step 5: End-to-end verification (do not skip) ━━━
5a. Offline self-checks (CST not required):
      & "<PYTHON>" tests\smoke_registry.py            # expect 84 tools, no duplicate names
      & "<PYTHON>" tests\check_mcp_compliance.py      # expect 17/17 passed
      & "<PYTHON>" tests\check_self_description.py    # expect problems found: 0
      & "<PYTHON>" tests\check_skill_tool_refs.py     # expect total missing references: 0
      & "<PYTHON>" tests\check_docs_consistency.py    # expect problems found: 0
      & "<PYTHON>" tests\test_audit_regressions.py    # expect 63/63 checks passed
      & "<PYTHON>" tests\test_port_info_verdict.py    # expect 13/13 checks passed

5b. Really call a tool once through the Harness (to prove the MCP is connected):
      cst_health_check_tool   {}
    Expect ready: true. If no cst_* tools are visible in the tool list at all,
    step 3 did not take effect — check the indentation, the paths, and whether you restarted.

5c. Minimal modelling verification (to prove it really can drive CST):
      cst_health_check_tool          {}
      cst_connect_tool               {"launch_if_needed": true}
      cst_new_project_tool           {"project_type": "mws"}
      cst_define_parameters_tool     {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6}}
      cst_create_brick_tool          {"component": "board", "name": "substrate",
                                      "xrange": ["-Lg/2","Lg/2"], "yrange": ["-Wg/2","Wg/2"],
                                      "zrange": ["-h","0"], "material": "PEC"}
      cst_set_solver_tool            {"solver": "HF Frequency Domain"}
      cst_set_frequency_range_tool   {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}
      cst_save_project_tool          {"path": "<CST_MCP_WORKSPACE>\\smoke_test.cst"}
      cst_model_audit_tool           {}
    Expect cst_model_audit_tool to return 1 solid, board:substrate, volume 4800 mm³.

5d. **Mandatory cleanup**:
      cst_quit_tool                  {}
    It closes all projects and releases the CST process. Skipping this step leaves behind
    modeler_AMD64.exe processes of about 700 MB each; once they accumulate, the next solve reports Not enough memory.

5e. To verify the full solve chain (optional, takes a long time):
      & "<PYTHON>" tests\verify_live.py       # expect 84/84 checks passed
      & "<PYTHON>" tests\run_123_task.py      # expect 30 calls, 0 failures

━━━ Step 6: Report back ━━━
Report using the format below; do not just say "it's installed":

  Environment : <CST-MCP> / <CST_ROOT> / <CST_EXE> / <PYTHON> / <SKILLS_DIR>
  MCP         : check_install --quick = ?/?   full = ?/?   RESULT = ?
  Tools       : number of cst_* tools in the Harness = ?   cst_health_check_tool ready = ?
  Skills      : whether both names appear in the skill list, and what they are
  Model       : whether board:substrate has a volume of 4800 mm³
  Cleanup     : whether cst_quit_tool released successfully
  Errors      : the raw error text from any step (copy it verbatim, do not reword it)

━━━ Hard rules ━━━
- If any step fails, **copy the raw error verbatim** before reporting; do not retell it as "it failed".
- Do not modify the test scripts, loosen assertions or skip steps just to make a check pass.
- Do not invent CST method names out of thin air. If the documentation says a command does not exist in 2026.2, it does not exist.
- When editing .env, keep the comments and the keys you did not touch.
- The target computer is offline: do not try to install anything over the network. If a dependency is missing, ask the user.
```

---

## 3. What You (the Human) Need to Prepare

Three things the AI cannot know on its own; telling it up front saves the most time:

1. **The real path of `<CST-MCP>` on the target computer** (for example `C:\CST-MCP`);
2. **Where CST is installed** (not needed if `check_install.py --fix` can find it automatically);
3. **Where the Harness's skills directory is**, and whether it has its own skill installation command.

Also: `CST_MCP_WORKSPACE` in `.env` must point at a **writable** directory, and must **not** be
mixed in with the CST installation directory.

---

## 4. Common Sticking Points (if the AI gets stuck, have it read this section)

| Where it sticks | Symptom | What to do |
|---|---|---|
| Step 1b | Every candidate Python fails to `import mcp` | The CST MCP already on the target computer must ship with a venv that has `mcp` installed; look for that one first |
| Step 2 | `--quick` reports `CST_INSTALL_ROOT` as unset, even though `.env` clearly sets it | Check that `.env` does not contain a placeholder such as `<CST_ROOT>`; `--fix` writes absolute paths |
| Step 3 | No `cst_*` tools are visible in the Harness | ① you did not restart; ② wrong YAML indentation; ③ wrong `command` or `mcp_server.py` path. Use section 5 of `check_install.py` to verify the server itself independently |
| Step 3 | `Cannot import 'cst.interface'` | `CST_INSTALL_ROOT` in `.env` is wrong; confirm with `Test-Path` |
| Step 4 | Neither of the two names is in the skill list | Check whether you copied the **directory** or only `SKILL.md`; the directory names must match what the Harness expects |
| Step 5c | `The specified material does not exist` | A library material must first be loaded into the project before a solid can reference it: call `cst_load_material_from_library_tool` first (this example uses PEC, which is a built-in material and needs no loading) |
| Step 5c | `Could not compute preconditioner.` | The model has features far smaller than the wavelength. Declare them with `cst_set_mesh_tool {"smallest_feature_mm": <smallest feature>}` |
| Any | `A command is used in the wrong thread context` | You reused a Design Environment left behind by another client. Call `cst_quit_tool` first, then `cst_connect_tool` |
| Any | The solve error looks like it was left over from the previous run | The CST message window **accumulates across calls**, so old ERRORs get mixed in. Only by checking whether `cst_list_results_tool` contains `S1,1` can you tell whether this run really failed |

**When troubleshooting, the AI should first read `tests\evidence\known_failures.md`** — it records the
6 classes of failure hit during development, the raw errors, the isolation experiments and the
conclusions, which is far faster than trial and error all over again.

---

## 5. Appendix: What Each File in the Package Is For

| File | For whom | Purpose |
|---|---|---|
| `docs\start\install.md` | The AI on the target computer | Execution-oriented installation steps (a more detailed companion to this file) |
| `README.md` | Human / AI | English overview, including **capabilities CST 2026.2 itself does not provide** |
| `skills\cst-studio-suite-mcp\SKILL.md` | AI | Tool catalogue and call order (details in its `references\`) |
| `skills\cst2026-simulation-execution\SKILL.md` | AI | Measured enumeration values, port criteria, mesh sizes, result validation (details in its `references\`) |
| `docs\mcp_tools.json` | AI | Machine-readable list of the 84 tools (read it when you need exact signatures) |
| `docs\extend\overview.md` | AI / human | How to keep adding tools |
| `tests\evidence\known_failures.md` | AI | **Pitfalls already hit; read this first when troubleshooting** |
| `tests\run_123_task.py` | AI | A complete task template you can copy (model → solve → produce evidence) |
| `check_install.py` | AI | Installation self-check, `--quick` / `--fix` / `--list-installs` |

### The Shape of a Skill Directory (copy this)

One skill = one directory; `SKILL.md` is the entry point and all the detail is split out into `references/`:

```text
cst-studio-suite-mcp\
├─ SKILL.md                              entry: front-matter + short routing
├─ metadata.json                         name / dir_name / category / status / source / license / description
├─ agents\openai.yaml                    display_name / short_description / default_prompt
└─ references\                           7 files: task classification / defaults / templates / tool catalogue / result validation / guard rails / extension
   ├─ workflow.md
   ├─ parameter-policy.md
   ├─ templates.md
   ├─ tool-catalogue-and-order.md
   ├─ result-validation.md
   ├─ guard-rails-and-limits.md
   └─ extending-and-conventions.md

cst2026-simulation-execution\
├─ SKILL.md
├─ metadata.json
├─ agents\openai.yaml
└─ references\
   ├─ solver-and-band.md
   ├─ ports-boundaries-mesh.md
   ├─ solve-verify-evidence.md
   └─ worked-example.md
```

`SKILL.md` should not be stuffed with long content — keep it a router, so the Agent loads only the one
reference it currently needs. This matches how the other skills in the hub are laid out.

---

## Related documents

* [Install](install.md) — the human-facing installation walkthrough
* [Upgrade](upgrade.md) — installing over an existing installation
* [Layout](../dev/layout.md) — what every file in the package is for
* [Skills](../dev/skills.md) — the two bundled agent skills
* [Installation check](../dev/verification.md) — what `check_install.py` verifies

