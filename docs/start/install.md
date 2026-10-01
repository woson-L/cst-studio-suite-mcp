# CST-MCP installation guide

> **Documentation index** › Installation

> **Want another AI to install it for you?** Hand it **`install-via-agent.md`** (self-contained
> bootstrap instructions), or copy section 2 of that file to it verbatim. This document is the
> detailed version of the same procedure, and following it works just as well.
>
> **Reader: the local model / AI agent on the target machine.**
> Work through this document in order and the installation is complete. Every step states what
> to run and what you should see when it succeeds.
> No network access is needed, and nothing has to be downloaded with `pip install`
> (the precondition is option A in step 1).

---

## 0. Goal and acceptance criteria

Install the `CST-MCP` folder on the target machine and wire it into Harness so that all of the
following hold:

1. `python check_install.py` prints **`RESULT: READY`**;
2. once Harness has started it lists **84 `cst_*` tools**;
3. calling `cst_health_check_tool` returns `"ready": true`;
4. calling `cst_connect_tool` starts or connects to a CST Design Environment and returns a pid.

Passing all four means the installation is complete. If any one fails, see section 8.

> **About the failures from `--quick`**: a freshly copied folder has no `.env`, so
> ```powershell
> python check_install.py --quick
> ```
> necessarily reports 3 FAILs in **section 3** (`.env` missing, `CST_INSTALL_ROOT` and
> `CST_DESIGN_ENVIRONMENT_EXE` not set), ending with
> `passed : 30  warning: 2  failed : 3` and `RESULT: NOT READY`.
> **This is normal** — sections 1–6 (Python, files, registry, 84 tools) should all PASS.
> Once `.env` has been written as described in section 3, re-running gives `failed : 0` and
> `RESULT: READY`.

---

## 0.1 Read this section first: what CST 2026.2 itself does not have (do not try to work around it)

These are not defects of this MCP; the CST VBA automation interface **does not provide them at
all**. When you hit a related error on the target machine, **do not spend time looking for an
alternative way to write it** — just follow the right-hand column.

| What you want to do | What CST 2026.2 actually does | What to do instead |
|---|---|---|
| **Generate or preview a mesh on its own** | **There is no such API.** The `Mesh` object only carries settings (`MeshType`, `StepsPerWavelengthTet`, `MinimumStepNumberTet` …); a bare `Mesh` statement reports `Default property usage is invalid`, and `Mesh.Create` / `Mesh.Reset` / `MeshGeneration` / `MeshAdaption3D.Create` do not exist at all (17 variants tested one by one) | Do not call `cst_generate_mesh_tool` (it only returns an error explaining this). The mesh is built by the solver, so use `cst_run_solver_tool` directly; supply mesh settings in advance with `cst_set_mesh_tool` |
| **Read the project's frequency unit** | `GetUnit ("Frequency")` reports `Expecting an already dimensioned array`; `GetUnit$` does not exist either | You must write `Units.GetUnit ("Frequency")` (with the `Units.` prefix). Note that `Units.SetUnit` conversely works without the prefix — the two are not symmetric |
| **Treat CST as a mesh/solver toolchain you can call separately** | The solver does not "mesh first and then wait for instructions"; it completes meshing and solving in one pass | A single `cst_run_solver_tool` call is enough |

When the model has a feature **far smaller than the wavelength** (for example a 2 mm gap at
0–100 MHz, where the wavelength is 3000 mm), you must tell the MCP that feature size
explicitly, otherwise the solve stops at `Could not compute preconditioner.`:

```
cst_set_mesh_tool  {"mesh_type": "Tetrahedral", "smallest_feature_mm": 2.0}
```

That parameter derives the required minimum mesh step count automatically from
`λ(fmax) / smallest_feature_mm`.

---

## 1. Pre-flight check: what is already on the target machine

### 1.1 Find out where CST is installed

```powershell
# search drive by drive, or just look in Program Files
Get-ChildItem "C:\Program Files" -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*CST*" }
```

You need two absolute paths (referred to below as `<CST_ROOT>` and `<CST_EXE>`):

```
<CST_ROOT> = for example  C:\Program Files\CST Studio Suite 2026
<CST_EXE>  = for example  C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe
```

Confirm that `<CST_EXE>` really exists:

```powershell
Test-Path "C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
# expected: True
```

### 1.2 Find a usable Python (the one with the `mcp` package installed)

CST-MCP needs a **Python 3.10+** whose interpreter can `import mcp`.
**If there is no `mcp`, you do not have to create a new environment** — the CST MCP already on
the target machine comes with an already installed `.venv`, and using it directly is simplest.

Try the options in the table below starting from A; **the first one that passes is the
interpreter you should use**. Note its full path — referred to below as `<PYTHON>`.

| Option | Interpreter path | Verification command | When it applies |
|---|---|---|---|
| **A (recommended)** | the venv of the existing CST MCP, for example `C:\CST-MCP\.venv\Scripts\python.exe` | see below | the target machine already has an older CST MCP |
| B | the Python bundled with CST: `<CST_ROOT>\Python\python.exe` | see below | the Python bundled with CST has `mcp` installed |
| C | the system Python: `python` (find its path with `where python`) | see below | system Python ≥3.10 that can install packages (network access) or already has `mcp` |

Verification commands (replace the path with the real one):

```powershell
& "<PYTHON>" --version
& "<PYTHON>" -c "import mcp, pydantic; print('mcp OK', mcp.__file__)"
```

Success looks something like:

```
Python 3.11.9
mcp OK C:\...\site-packages\mcp\__init__.py
```

- If all three options fail: if the target machine **has network access**, run
  `& "<PYTHON>" -m pip install "mcp>=1.10,<2" pydantic`;
  if it is **completely offline**, the only options are to find an existing venv elsewhere, or to
  copy the whole `.venv\Lib\site-packages\mcp` directory over from this machine.
  **Do not** continue with the following steps on an interpreter that has no `mcp`.

### 1.3 Identify the old CST MCP directory (the one being replaced)

```powershell
# common locations; pick the one that exists
Test-Path "C:\CST-MCP"
Test-Path "C:\CST-MCP"
Test-Path "C:\CST-MCP"
```

Note the one that exists as `<OLD_MCP>`. It should contain `mcp_server.py` and `cst_automation.py`.

---

## 2. Putting the files in place

Copy the whole `CST-MCP` folder to the target machine, for example to `C:\CST-MCP`.

**Two ways to wire it in, pick one:**

### Way one (recommended): overwrite the old directory

Whatever is in the old MCP directory does not matter: the new version carries every file it needs.

```powershell
# back up the old directory first (to keep .env and .venv, see way two)
Move-Item "<OLD_MCP>" "<OLD_MCP>_backup"

# put the new directory in its place
Move-Item "C:\CST-MCP" "<OLD_MCP>"
```

After the overwrite `<OLD_MCP>` is the new CST-MCP. **Also copy the `.venv` from the old
directory back** (if you chose option A in step 1):

```powershell
Copy-Item "<OLD_MCP>_backup\.venv" "<OLD_MCP>\.venv" -Recurse
```

### Way two: keep both, only repoint Harness

Leave the old directory untouched and point Harness at the new directory `C:\CST-MCP` (see
step 4).

> **Note**: with either way, the `.env` file is not in the release package (only the template
> `.env.example` is). Step 3 creates it.

---

## 3. Writing the `.env` configuration file

Change into the CST-MCP directory and create it from the template:

```powershell
Set-Location "C:\CST-MCP"
Copy-Item .env.example .env
notepad .env
```

Change the contents to the following (**change only these four values**, using the real paths
found in step 1):

```ini
# ---- CST installation location ----
CST_INSTALL_ROOT=C:\Program Files\CST Studio Suite 2026
CST_DESIGN_ENVIRONMENT_EXE=C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe

# ---- working directories (projects created through the MCP are saved here) ----
CST_MCP_WORKSPACE=C:\CST_MCP_workspace
CST_MCP_EVIDENCE=C:\CST_MCP_workspace\evidence

# ---- optional, leaving them at their defaults is fine ----
CST_RUNTIME_CLI_TIMEOUT=120
CST_MCP_QUIET=1
```

Key points:

- **The paths must be absolute paths** — do not leave `<...>` placeholders in them;
- use a directory on a **local disk with plenty of free space** for `CST_MCP_WORKSPACE` (one
  project plus its results is tens to hundreds of MB);
- leave every line other than these four keys exactly as the template has it.

After editing, confirm the file contents (**do not** leave `<...>` in it):

```powershell
Get-Content .env | Where-Object { $_ -notmatch "^\s*#" -and $_.Trim() -ne "" }
```

---

## 4. Wiring it into Harness / an MCP client

The Harness on the target machine is DSH. Its MCP configuration lives in the **patch layer of
the profile**:

```
<DSH_HOME>\.dsh\profiles\<profile name>\cordis.patch.yml
```

`<DSH_HOME>` is usually `C:\Users\<username>\.dsh` (if the `DSH_HOME` environment variable is
set, that takes precedence). If you cannot find it, just search:

```powershell
Get-ChildItem "$env:USERPROFILE\.dsh" -Recurse -Filter "cordis.patch.yml" -ErrorAction SilentlyContinue | Select-Object FullName
```

Append the following to the end of that file (**an existing entry with the same id must be
replaced — there must not be two**):

```yaml
# --- CST Studio Suite MCP ---
- id: mcp-cst-studio-suite
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: cst-studio-suite
    transport: stdio
    command: C:\CST-MCP\.venv\Scripts\python.exe
    args:
      - C:\CST-MCP\mcp_server.py
    cwd: C:\CST-MCP
```

- `command` takes the `<PYTHON>` chosen in step 1; **backslashes must be written as `\\` or kept
  as single backslashes** (a single backslash is usable in YAML, but do not write sequences such
  as `\t` or `\n` that get interpreted; when a path contains `\t`, write `\\t`);
- `args` must point at the absolute path of **`mcp_server.py`**;
- set `cwd` to the CST-MCP directory — `.env` is right there, and the server reads it by itself
  on startup;
- **do not** repeat the CST paths under `env:` — `.env` is enough; writing them causes no error
  either, but if the two disagree, `env` wins.

After the change, **restart Harness** (the MCP server is a stdio child process and is not hot
reloaded).

> If the target machine uses a client other than DSH (Codex / Claude Desktop and the like),
> write the equivalent three items into its MCP configuration: the command `<PYTHON>`, the
> argument being the absolute path to `mcp_server.py`, and the working directory being the
> CST-MCP directory.

---

## Skill composition

This package ships two skills, divided by **question** rather than by tool:

| Skill | What it answers |
| --- | --- |
| `cst-studio-suite-mcp` | what to do (mode), what may be left at its default, which template to pick, which tool to call in which order, which evidence a report needs |
| `cst2026-simulation-execution` | which enumeration values are legal, whether this result can be trusted |

`cst-studio-suite-mcp` also covers the task typing, default values and reporting requirements of
the previously separate workflow skill; that skill no longer exists (a backup is kept in
`CST-MCP-superseded/` outside this directory, there if you need to roll back).

---

## 5. Verification (do it in order; every step has an explicit expectation)

### 5.1 Static checks (CST does not need to be started)

```powershell
Set-Location "C:\CST-MCP"
& "<PYTHON>" check_install.py --quick
```

Expected ending:

```
== Summary ==
  passed : 30
  warning: 2
  failed : 3

  Problems:
    - .env: missing - copy .env.example to .env and set the CST paths (see docs/start/install.md step 3)
    - CST_INSTALL_ROOT: not set - edit .env, or run: python check_install.py --fix
    - CST_DESIGN_ENVIRONMENT_EXE: not set - edit .env, or run: python check_install.py --fix
```

**First confirm that sections 1, 2 and 4 are all PASS** (Python and packages, the 7 tool
modules, 84 tools, no duplicate names).
The 3 FAILs in section 3 are because `.env` has not been written yet and are expected.

After writing `.env`, run it once more; it should become:

```
== Summary ==
  passed : 44
  failed : 0
RESULT: READY - point your MCP client at this folder:
  command = <PYTHON>
  args    = ["C:\CST-MCP\mcp_server.py"]
  cwd     = C:\CST-MCP
```

### 5.2 Full check (includes the MCP handshake and a real connection to CST)

```powershell
& "<PYTHON>" check_install.py
```

Expect sections 5 and 6 to be all PASS:

```
== 5. MCP handshake (what the model's client does) ==
  [PASS] initialize  server=cst-studio-suite-mcp
  [PASS] tools/list  84 tools
  [PASS] tool cst_health_check_tool  available

== 6. CST availability ==
  [PASS] cst_health_check_tool  ready=True interface=True results=True
  [PASS] cst_connect_tool  pid=xxxxx

RESULT: READY
```

### 5.3 Confirm inside Harness that the tools are loaded

After restarting Harness, have it call:

```
cst_health_check_tool   {}
```

Expect `"ready": true`. If **no `cst_*` tool is visible** in the tool list, the configuration
from step 4 has not taken effect — check the indentation in `cordis.patch.yml` (it must be
2 spaces, with `config:` at the same level as `id:`/`name:`) and whether the `command` path
exists.

### 5.4 Minimal end-to-end verification (proves CST can really be operated)

```
cst_health_check_tool          {}          # look at resources: free memory and CST worker count
cst_connect_tool               {"launch_if_needed": true}
cst_new_project_tool           {"project_type": "mws"}
cst_define_parameters_tool     {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6}}
cst_create_brick_tool          {"component": "board", "name": "substrate",
                                "xrange": ["-Lg/2","Lg/2"], "yrange": ["-Wg/2","Wg/2"],
                                "zrange": ["-h","0"], "material": "PEC"}
cst_set_solver_tool            {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool   {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}
cst_save_project_tool          {"path": "C:\\CST_MCP_workspace\\smoke_test.cst"}
cst_model_audit_tool           {}
cst_quit_tool                  {}          # wrap up: close all projects and release CST
```

`cst_model_audit_tool` should return 1 solid, `board:substrate`, with a volume of 4800 mm³.
**At that point the installation is complete.**

Note that the `unit` of `cst_set_frequency_range_tool` is really written into the project
(`Units.SetUnit`), and `fmin`/`fmax` are interpreted in the unit you give.

To verify the complete solve flow (including a real solve and S-parameter export):

```powershell
& "<PYTHON>" tests\verify_live.py       # expect 84/84 checks passed
& "<PYTHON>" tests\run_123_task.py      # example task: cube + thin plate + discrete port, expect 30 calls with 0 failures
```

`tests\run_123_task.py` is a complete template you can copy verbatim: modelling → material →
port → solver → frequency band → mesh → solve → read S-parameters → export. It prints the tool
name and the arguments of every call, one by one.

---

## 6. Tool inventory and call order

**84 tools** in all, 14 categories. The complete definitions (with JSON Schema, examples and
notes) are in **`docs\mcp_tools.json`** — read it when you need exact signatures.

| Category | Count | Purpose |
|---|---|---|
| `session` | 14 | health check, connect, project create/open/save/close, message window, raw VBA, history blocks |
| `parameters` | 4 | read/create/change/delete design parameters |
| `geometry` | 14 | brick, cylinder, sphere, cone, torus, elliptical cylinder, bond wire, boolean, transform, extrude, components |
| `material` | 3 | create a material, assign a material, load from the material library |
| `port` | 3 | discrete port, waveguide port, list ports |
| `solver` | 11 | solver selection, frequency range, frequency-domain/time-domain/eigenmode configuration, boundary, symmetry, background, solve |
| `mesh` | 2 | mesh type and density (including `smallest_feature_mm`). **Note: there is no "generate mesh" tool**, see section 0.1 for why |
| `monitor` | 2 | add/list field monitors |
| `results` | 2 | result tree, read 1D results |
| `verify` | 5 | S11, reference impedance, port info, power budget, model audit |
| `export` | 3 | Touchstone, ASCII, summary JSON |
| `sweep` | 2 | parameter sweep: preview the case count, then run it case by case |
| `runtime` | 16 | built-in command bridge + typed wrapper generation (8 implementations, bidirectional aliases) |
| `meta` | 3 | list tools, generate the manifest, dynamic invocation |

**Standard order** (every step can be retried independently):

```
1  environment   cst_health_check_tool → cst_detect_tool → cst_connect_tool
2  project       cst_new_project_tool (saved into the workspace automatically) / cst_open_project_tool
3  parameters    cst_get_parameters_tool → cst_define_parameters_tool / cst_set_parameters_tool
4  modelling     cst_create_* / cst_boolean_tool / cst_transform_tool / cst_add_to_history_tool
5  materials     cst_load_material_from_library_tool / cst_create_material_tool / cst_assign_material_tool
6  ports         cst_add_discrete_port_tool / cst_add_waveguide_port_tool → cst_list_ports_tool
7  solver        cst_set_solver_tool → cst_set_frequency_range_tool → cst_configure_*_solver_tool
8  domain & mesh cst_set_boundary_tool / cst_set_symmetry_tool / cst_set_mesh_tool / cst_add_monitor_tool
9  solve         cst_save_project_tool → cst_run_solver_tool → cst_messages_tool
                 (**there is no separate "generate mesh" step**: the mesh is built by the solver, see section 0.1)
10 verification  cst_read_s11_tool / cst_read_reference_impedance_tool / cst_read_port_info_tool
11 evidence      cst_export_touchstone_tool / cst_export_ascii_tool / cst_write_summary_json_tool
```

**Wrapping up**: call `cst_quit_tool` when a task is finished; it closes **all** open projects
and releases the Design Environment process. Every open 3D project occupies about 700 MB of
`modeler_AMD64.exe`, and if it is not released the memory accumulates until it runs out, at
which point the next solve reports `Not enough memory`.

---

## 7. Three hard rules (breaking them yields wrong results or hangs CST)

### 7.1 Parameters may only be changed with `cst_set_parameters_tool`

**Never** put `StoreParameter` / `StoreParameters` / `Rebuild` into the `vba_code` of
`cst_add_to_history_tool`.

- CST 2026 reports `The rebuild operation cannot be used inside a structure macro.`;
- in testing such a block also **hangs** the Design Environment, after which every call gets no
  response and the process can only be killed.

The server already intercepts this inside `cst_add_to_history_tool`: it returns an error
outright for code like that and tells you the correct approach — when you see that error,
switch to `cst_set_parameters_tool` and do not work around it.

### 7.2 Save before solving, and set the frequency range first

The order must be: set the solver → set the frequency range → save → solve.
A missing frequency range reports `Solver run failed. Frequency range not set correctly.`

### 7.3 A successful solve does not mean a correct result: the port must be checked

After every solve, check these two things:

```
cst_read_reference_impedance_tool   # must equal the impedance you want (50Ω discrete port should return 50+0j)
cst_read_port_info_tool             # the cutoff frequency must be far below the operating band
```

A pitfall actually hit in practice: a waveguide port on the cross-section of a microstrip line —
the solve succeeds and `S1,1` is in the result tree, but the port cutoff frequency is
**51.9 GHz** and the wave impedance **6.2 kΩ**, the mode is cut off in the operating band, S11
is a flat line at −0.6 dB, and the reference impedance is **7623 Ω instead of 50 Ω** — it looks
like an antenna, but it is actually meaningless.

---

## 8. Troubleshooting

| Symptom | Cause | What to do |
|---|---|---|
| `check_install.py` reports `package 'mcp' missing` | the interpreter in use has no mcp installed | go back to step 1.2 and switch interpreters |
| `Cannot import 'cst.interface'` | `CST_INSTALL_ROOT` in `.env` is wrong | step 3: write an absolute path and confirm it with `Test-Path` |
| `cst_exe_exists: false` | same as above | same as above |
| `There is no active CST project currently.` | the project is still in CST's Temp directory | use `cst_new_project_tool` (it saves into the workspace automatically); open an old project with `cst_open_project_tool` |
| no `cst_*` tool is visible in Harness | `cordis.patch.yml` has not taken effect | check the indentation, the paths and whether you restarted; section 5 of `check_install.py` can verify the server itself independently |
| `cst-runtime-cli scripts not found` | an old `cst_runtime_*` implementation is in use | the new version has the command bridge built in, so this should no longer appear; if it does, `cst_mcp\tools\runtime_tools.py` is missing |
| CST does not respond / every later call hangs | someone put parameter code into a history block | kill `CST DESIGN ENVIRONMENT_AMD64.exe` and every `modeler_AMD64.exe`, then reconnect; switch to `cst_set_parameters_tool` |
| `Error during construction of pre-conditioner. Not enough memory.` | **out of memory**: a failed solve or an unreleased project leaves `modeler_AMD64.exe` behind, about 700 MB each | call `cst_quit_tool` to release all projects and the DE; the `resources` field of `cst_health_check_tool` reports free memory and the worker count; if memory is short before a solve, `cst_run_solver_tool` stops it outright |
| `Could not compute preconditioner.` (**without** the word memory) | **the mesh does not resolve the small feature**: element size is taken from the wavelength alone, while the model contains a gap/thickness far smaller than the wavelength | `cst_set_mesh_tool {"mesh_type":"Tetrahedral","smallest_feature_mm":<smallest feature>}`, see section 0.1 |
| `Default property usage is invalid. (Mesh)` | some code issued a bare `Mesh` statement | do not call `cst_generate_mesh_tool`; CST has no standalone meshing API, so use `cst_run_solver_tool` directly |
| `A command is used in the wrong thread context` | you reused a Design Environment **left behind by another client**, and its thread context is no longer yours | call `cst_quit_tool` first, then `cst_connect_tool`, to get a brand-new DE. **This does not mean the tools are broken** |
| `Expecting an already dimensioned array. (u = GetUnit(...))` | a bare `GetUnit` does not exist | write `Units.GetUnit ("Frequency")`, with the `Units.` prefix |
| `Terminated on unknown error` | a lack of information that only the old version had | the new version attaches the raw CST message window text; act on the `ERROR:` lines in it |
| the error reported by a solve looks like it was left over from the previous one | the message window **accumulates across calls**, so an older ERROR mixes into this run's result | cross-check with `cst_list_results_tool`: only if the result tree has no `S1,1` at all did this run really fail |
| `unknowntool cst_...` | the tool name is misspelled | read `docs\mcp_tools.json` or call `cst_list_mcp_tools_tool` |
| a solve is very slow / fails although the model is simple | the port, frequency range or mesh settings are unreasonable | use `cst_frequency_overview_tool` to see the solver + frequency band + monitors in one go |

---

## 9. Extending the tools later (how to add a missing capability)

Tools are registered one module per category, so **adding a capability does not require changing
the server core**:

1. create `<your module>.py` under `cst_mcp\tools\`;
2. define `register_tools(registry)` in it and register with `registry.tool(...)`;
3. restart Harness — on startup the server automatically scans every module under `cst_mcp.tools`.

```python
from ..registry import ToolRegistry
from ..session import session

def register_tools(registry: ToolRegistry) -> None:
    @registry.tool(
        "cst_my_tool",              # must start with cst_
        "One sentence saying what this tool does.",
        "custom",                   # category; it shows up in the manifest
        params={"solid": "str"},
        required=["solid"],
        examples=[{"solid": "board:ground"}],
        replaces_vba="TheCstObject.TheMethod",   # which CST command it corresponds to
    )
    def my_tool(solid: str) -> dict:
        return session().add_history("my block", f'Solid.ChangeMaterial "{solid}", "PEC"')
```

New tools appear automatically in `cst_list_mcp_tools_tool` and in the regenerated
`docs\mcp_tools.json`. The detailed contract is in `docs\EXTENDING.md`.

**The recommended way to add a tool**: first click through the operations you want with CST's
macro recorder, paste the recorded VBA into the tool, then replace the numbers with parameter
names — that way the method names are guaranteed to be right. Every CST command name in this
package was tested on CST 2026.2, so **do not write CST method names from memory** (for example
`MaterialUnit`, `Color` and `Monitor.GetName` look right but do not exist on 2026.2).

---

## 10. Appendix: directory layout

```
CST-MCP\
├─ README.md                    overview and documentation index
├─ mcp_server.py                MCP entry point (the MCP client must point at it)
├─ check_install.py             install self-check (--quick / --fix / --list-installs)
├─ .env.example                 .env template
├─ cst_mcp\
│  ├─ config.py                 .env loading, CST paths, working directories
│  ├─ session.py                CST session: Design Environment, projects, VBA, results, release
│  ├─ lint.py                   safety interception for history blocks and parameter values (incl. parameter-name injection protection)
│  ├─ registry.py               extensible tool registry
│  ├─ vba\geometry.py           geometry VBA generation (method names already tested)
│  └─ tools\                    one module per category, each with register_tools()
├─ docs\
│  ├─ README.md                 grouped documentation index
│  ├─ start\
│  │  └─ install.md             this file
│  ├─ use\                      quick start, usage, tool catalogue, rules, limits
│  ├─ extend\                   adding tools and tool families
│  ├─ dev\                      layout, skills, verification
│  └─ mcp_tools.json            machine-readable manifest of all 84 tools (for the AI to read)
├─ skills\                      one directory per skill: SKILL.md + metadata.json
│  │                            + agents\openai.yaml + references\*.md
│  ├─ cst-studio-suite-mcp\     task typing/defaults/templates/tool order/result validation (7 references)
│  └─ cst2026-simulation-execution\  enumeration values, port/mesh criteria, result validation, troubleshooting
└─ tests\
   ├─ smoke_registry.py         offline: registry + manifest
   ├─ check_mcp_compliance.py   offline: MCP protocol compliance
   ├─ check_self_description.py offline: workflow/description/example self-consistency
   ├─ check_skill_tool_refs.py  offline: every tool name referenced in a skill exists
   ├─ check_skill_layout.py     offline: skill directory layout (SKILL.md/metadata/openai.yaml/references)
   ├─ check_docs_consistency.py offline: the tool names and example parameters in the documentation are all valid
   ├─ test_audit_regressions.py offline: regression tests for every past bug
   ├─ test_port_info_verdict.py offline: port-verdict threshold regression tests
   ├─ verify_live.py            live: the complete chain (including a real solve)
   ├─ verify_fixes_live.py      live: targeted verification of already fixed tools
   ├─ probe_commands.py         live: probe a single CST VBA command
   ├─ run_123_task.py           live: the full example task (copy it and adapt it to your own)
   └─ evidence\                 verification logs, exported .s1p files, and known_failures.md
```

### Offline self-checks (no CST needed, runnable right after installation)

```powershell
Set-Location "C:\CST-MCP"
$py = "<PYTHON>"
& $py tests\smoke_registry.py           # expect: 84 tools, no duplicate names
& $py tests\check_mcp_compliance.py     # expect: 17/17 passed
& $py tests\check_self_description.py   # expect: problems found: 0
& $py tests\check_skill_tool_refs.py    # expect: total missing references: 0
& $py tests\check_skill_layout.py       # expect: problems found: 0
& $py tests\check_docs_consistency.py   # expect: problems found: 0
& $py tests\test_audit_regressions.py   # expect: 63/63 checks passed
& $py tests\test_port_info_verdict.py   # expect: 13/13 checks passed
```

### Live verification (requires CST to be launchable)

```powershell
& $py tests\verify_live.py              # complete chain, expect 84/84 checks passed
& $py tests\verify_fixes_live.py        # targeted verification, expect 28 passed, 0 failed
& $py tests\run_123_task.py             # example task, expect 30 calls with 0 failures
```

**Verification status** (measured in practice on the same CST 2026.2 installation, 2026-09-11):

| Item | Result |
|---|---|
| `check_install.py` (after `.env` is configured) | 44/44 (`--quick`), 58/58 (full) |
| `check_mcp_compliance.py` | 17/17 |
| `check_self_description.py` | 0 problems |
| `check_skill_tool_refs.py` | 0 missing |
| `check_skill_layout.py` | 0 problems |
| `check_docs_consistency.py` | 0 problems |
| `test_audit_regressions.py` | 63/63 |
| `test_port_info_verdict.py` | 13/13 |
| `test_save_overwrite.py` | 14/14 |
| `verify_live.py` (real solve) | 84/84 |
| `verify_fixes_live.py` | 28/28 |

**The pitfalls hit during development, with the original error messages, are recorded in
`tests\evidence\known_failures.md`** — 7 classes of failure symptom, the isolation experiments
and the conclusions drawn. Read it first when troubleshooting a difficult problem. The per-run
logs and exported S-parameters it references are not committed; re-running the corresponding
runner regenerates them.

---

## Related documents

* [Install via another agent](install-via-agent.md) — hand the installation to an AI
* [Upgrade](upgrade.md) — installing over an existing installation
* [Quick start](../use/quickstart.md) — first run and first tool call
* [Verification](../dev/verification.md) — every check and what it proves
* [Layout](../dev/layout.md) — the repository tree with per-file notes
* [What CST 2026.2 does not expose](../use/cst-2026-limits.md) — check here before filing a bug
