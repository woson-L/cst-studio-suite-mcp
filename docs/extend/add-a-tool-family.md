# Adding a tool family by hand — a standalone manual

> **Audience: the human or AI who adds a capability to CST-MCP by hand on the target machine.**
> This document is self-contained; no other document needs to be read. It uses the real
> "parameter sweep" tool family as the example: steps you can **follow directly**, an acceptance criterion for each, and the **traps hit in live testing**.
>
> Work through this document and you end up with a tool family equivalent to the bundled `cst_mcp/tools/sweep_tools.py`.

---

## 0. Understand the extension mechanism first (30 seconds)

```
mcp_server.py
  ├── registry = ToolRegistry()
  ├── registry.discover_extensions("cst_mcp.tools")   ← scans every module under cst_mcp/tools/
  │       each module's register_tools(registry) is called
  ├── registers every spec as an MCP tool
  └── build_manifest()                                 ← the manifest is generated from the registry, so it cannot drift
```

**The key conclusion, which decides where you put your files:**

| Where you put your file | Auto-discovered? |
|---|---|
| `cst_mcp/tools/<name>_tools.py` | ✅ yes — as long as it defines `register_tools(registry)` |
| the **top level** of the package (such as `cst_parameter_sweep.py`) | ❌ **no** — it must be imported by one of the modules above, and written into `pyproject.toml` |

So the typical shape of a tool family is:

```
cst_mcp/tools/<family>_tools.py   ← the only file that touches the registry (auto-discovered)
<top-level helper 1>.py           ← pure logic, no CST dependency
<top-level helper 2>.py           ← the part that relates to a CST session
pyproject.toml                    ← lists the top-level modules under py-modules
```

---

## 1. Step one: write the top-level helper modules (optional, but this split is recommended)

Keep the **logic that does not need CST** at the top level on its own: the benefit is that it can be tested on a machine without CST installed.

For the sweep example, the top-level module holds:

- parameter-spec parsing (`"48:52:2"` → `[48, 50, 52]`)
- case expansion (the three modes `cartesian` / `single` / `zip`)
- a ceiling guard (exceeding `max_cases` raises instead of running away)
- the per-case runner (copy the project → change the parameters → optional solve → export)

**Acceptance criterion**: `python -c "import <module_name>"` succeeds and imports no `cst.*`.

---

## 2. Step two: write the registration module

Create `cst_mcp/tools/<family>_tools.py`. The skeleton is below (**a complete, runnable example is in section 4**):

```python
"""One sentence saying what this tool family does."""
from __future__ import annotations

from typing import Any

from .. import config
from ..registry import ToolRegistry

CATEGORY = "sweep"          # becomes a manifest category


def register_tools(registry: ToolRegistry) -> None:

    @registry.tool(
        "cst_sweep_preview_tool",                    # must start with cst_ and end with _tool
        "One-sentence summary (shown to the agent).", # required
        CATEGORY,                                    # required
        params={"parameters": "dict", "mode": "str", "max_cases": "int"},
        required=["parameters"],
        returns="{ok, mode, case_count, parameters, cases}",
        examples=[{"parameters": {"L": "48:52:2"}, "mode": "single"}],
        notes=["Anything the caller must know, one item per line."],
        replaces_vba="(state it honestly when there is no matching CST command)",
    )
    def sweep_preview(parameters: dict, mode: str = "cartesian",
                      max_cases: int = 200) -> dict[str, Any]:
        # import inside the function: with the helper module missing, the other tools still work
        from cst_parameter_sweep import preview_sweep
        return preview_sweep(parameters=parameters, mode=mode, max_cases=max_cases)
```

### Three conventions you must follow

1. **Import optional dependencies inside the handler**, not at the top of the module. Otherwise a single missing helper module stops the whole server from starting.
2. **Return a `dict`**, never a string — MCP surfaces it as structured content, which is what lets the agent parse it.
3. **Read back anything you changed.** Put the value read back from CST into the return value. That is the difference between "the call succeeded" and "the change took effect".

### How to write the `params` type hints

| hint | generated JSON Schema |
|---|---|
| `"str"` | `{"type": "string"}` |
| `"int"` | `{"type": "integer"}` |
| `"float"` | `{"type": "number"}` |
| `"bool"` | `{"type": "boolean"}` |
| `"dict"` | `{"type": "object"}` |
| `"list"` | `{"type": "array"}` |
| `"str | null"` | `{"type": ["string", "null"]}` |

Keys written into `required` go into the schema's `required`, so the client rejects an invalid call before your code runs.

---

## 3. Step three: edit `pyproject.toml`

If you added a **top-level** module (not under `cst_mcp/tools/`), you must declare it, otherwise it disappears after `pip install`:

```toml
[tool.setuptools]
py-modules = [
    "mcp_server",
    "cst_automation",        # ← your top-level module
    "cst_schematic",
    "cst_parameter_sweep",
]
```

**Acceptance criterion**:

```powershell
python check_install.py --quick
# expected to contain:
#   [PASS] py-modules  N declared, all present
#   [PASS] top-level modules  all declared in pyproject.toml
```

> If you only run `python mcp_server.py` straight from the source folder (no pip install), a missing
> declaration does **not** raise immediately, but the package produced by `pip install` will be missing files. So declare it; do not skip it.

---

## 4. Complete example: the two sweep tools

### 4.1 The preview tool (**never touches CST**)

```python
    @registry.tool(
        "cst_sweep_preview_tool",
        "Expand a parameter sweep spec into concrete cases and report the case count. Does not start CST.",
        CATEGORY,
        params={"parameters": "dict", "mode": "str", "max_cases": "int"},
        required=["parameters"],
        returns="{ok, mode, case_count, parameters, cases}",
        examples=[{"parameters": {"L": "48:52:2"}, "mode": "single"},
                  {"parameters": {"L": [48, 50], "w": [2, 3]}, "mode": "cartesian",
                   "max_cases": 20}],
        notes=[
            "Call this BEFORE cst_sweep_run_tool: it is the cheap half - it opens no CST and writes no file.",
            "Show the case count to the user first when the count is large or the cases will be solved.",
            "Value specs accept a list [48, 50] or a range string 'start:stop:step'.",
            "mode: single (vary the first parameter only) / zip (pair values, shortest wins) / cartesian (all combinations).",
            "max_cases is a guard, not a target: exceeding it raises instead of running.",
        ],
        replaces_vba="(no matching CST command — pure case enumeration)",
    )
    def sweep_preview(parameters: dict, mode: str = "cartesian",
                      max_cases: int = 200) -> dict[str, Any]:
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError('parameters must be a non-empty object, for example {"L": "48:52:2"}')
        from cst_parameter_sweep import preview_sweep
        return preview_sweep(parameters=parameters, mode=mode, max_cases=max_cases)
```

**Why this tool has to be split out**: it is the only step that turns "sweep L and w" into "6 cases in total".
Without it, the caller can only start running blindly.

### 4.2 The execution tool

```python
    def _manager():
        """Build a connected CST session manager. Two traps are explained below."""
        config.load_env()                       # trap 2: a top-level module does not read .env automatically
        from cst_automation import CSTSessionManager
        manager = CSTSessionManager()
        try:
            manager.connect(launch_if_needed=False)   # attach if you can; do not launch a second CST
        except Exception:
            manager.connect(launch_if_needed=True)    # trap 3: otherwise "No DEs found"
        return manager

    @registry.tool(
        "cst_sweep_run_tool",
        "Run a parameter sweep: one copied project per case, parameters applied, optional solve and export.",
        CATEGORY,
        params={"project_path": "str", "parameters": "dict", "output_dir": "str | null",
                "mode": "str", "run_solver": "bool", "export_touchstone": "bool",
                "result_tree_paths": "list | null", "max_cases": "int",
                "overwrite": "bool", "continue_on_error": "bool",
                "close_after_case": "bool", "result_max_points": "int"},
        required=["project_path", "parameters"],
        returns="{ok, mode, case_count, completed, failed, output_dir, summary_csv, manifest}",
        examples=[{"project_path": "C:\\\\proj\\\\123.cst",
                   "parameters": {"L": "48:52:2"}, "mode": "single",
                   "run_solver": False}],
        notes=[
            "Does not modify the source project: each case gets its own copy.",
            "run_solver defaults to False - cheap and safe by default; a 100-case sweep with solves can take hours.",
            "Output defaults to <source project folder>/sweeps/<project name>_<timestamp>/, independent of CST_MCP_WORKSPACE.",
            "Read sweep_summary.csv (the per-case table) and sweep_manifest.json (the full record);",
            "do not report success or failure from memory.",
            "Always preview first with cst_sweep_preview_tool.",
        ],
        replaces_vba="(no single CST command — orchestrates per-case parameter changes)",
    )
    def sweep_run(project_path: str, parameters: dict, output_dir: str | None = None,
                  mode: str = "cartesian", run_solver: bool = False,
                  export_touchstone: bool = False,
                  result_tree_paths: list | None = None, max_cases: int = 200,
                  overwrite: bool = False, continue_on_error: bool = True,
                  close_after_case: bool = True,
                  result_max_points: int = 2000) -> dict[str, Any]:
        from pathlib import Path
        source = Path(project_path).expanduser()
        if not source.is_file():
            raise ValueError(f"project does not exist: {source}")
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters must be a non-empty object")
        from cst_parameter_sweep import CSTParameterSweepRunner
        runner = CSTParameterSweepRunner(_manager())
        return runner.run_sweep(
            project_path=str(source), parameters=parameters, output_dir=output_dir,
            mode=mode, run_solver=run_solver, export_touchstone=export_touchstone,
            result_tree_paths=list(result_tree_paths) if result_tree_paths else None,
            max_cases=max_cases, overwrite=overwrite,
            continue_on_error=continue_on_error, close_after_case=close_after_case,
            result_max_points=result_max_points)
```

---

## 5. Five traps hit in live testing (**follow this document and you avoid them**)

### Trap 1 — a top-level module that is not declared disappears once installed

Only `cst_mcp/tools/*.py` is auto-discovered. A top-level module runs fine from the source folder, and
after `pip install` it is **not in the package**. See section 3, which `check_install.py` verifies.

### Trap 2 — `.env` is not loaded automatically

`cst_mcp.config.load_env()` writes `.env` into `os.environ`.
The core tools get that automatically because they import `cst_mcp`; **a top-level module that reads
`os.environ["CST_INSTALL_ROOT"]` directly does not**. You must call `config.load_env()` by hand once before using it.

Symptom: `cannot import 'cst.interface'`, and the reported path points at a drive letter that does not exist (the fallback default built into the module).

### Trap 3 — `CSTSessionManager.connect()` does not launch CST

It only ever **attaches to an already running** Design Environment. With none open, every case fails with:

```
RuntimeError: No DEs found to connect to.
```

The correct form is "attach if you can, launch only if you cannot" (section 4.2), so a CST that already has a project open is reused instead of being launched a second time.

### Trap 4 — a parameter change must go through `execute_vba`, **not** `add_to_history`

This one fails in **two different ways**, both verified live:

| Attempt | CST answer |
|---|---|
| bare block into `add_to_history` | `The rebuild operation cannot be used inside a structure macro.` / `Prevented attempt to change the value for parameter X inside history rebuild` — and it can **leave the Design Environment stuck**, with every later call hanging |
| `Sub Main` block into `add_to_history` | `Unterminated block ... in add_to_history` — `add_to_history` wants a history block, not a macro |
| bare block into `execute_vba` | **works** — it adds the `Sub Main` wrapper itself and calls `_execute_vba_code` |

Conclusion: **build a bare VBA block and hand it to `execute_vba()`.**
That is the same immediate-execution channel `cst_mcp.session.set_parameters()` uses.

### Trap 5 — a library material is not saved with the project (**this one ruins the whole sweep**)

Observed in live testing:

```
MaterialLibrary.LoadMaterialFromLibrary ("Iron", "", True)
```

a loaded material is **not persisted into the `.cst`**. After saving, reopening the project and triggering a rebuild fails at the solid that uses that material:

```
(&H8000ffff) The specified material does not exist: Iron
(.Create)
```

And **changing a parameter necessarily triggers a rebuild**, so:

> **A parameter sweep over any project that uses a "library material" fails in every case.**

Observed behaviour of the two halves:

- the parameter value **is** written (with `StoreParameters` alone and no rebuild it succeeds and reads back);
- but the geometry **does not follow**, because the rebuild cannot replay the history that created that solid.

Three recommendations for anyone extending this:

1. For a model that must rebuild in a later session, **prefer a material defined in the project**
   (`cst_create_material_tool`) rather than one loaded from the material library;
2. Before sweeping any project, **first confirm that it "still rebuilds after being reopened"** — that, not the
   sweep code, is the usual reason every case fails;
3. Seeing `StoreParameters` succeed **is not** enough to call a case successful: read the parameter value back **and** confirm the geometry moved.

---

## 6. Acceptance checklist (tick each item when done)

```powershell
cd <CST-MCP>

# 1) registration works, no duplicate names, the manifest is updated
python tests\smoke_registry.py
#   expected: registered tools: 84 (or your number after adding tools)
#         duplicate tool names: none

# 2) descriptions / categories / examples are self-consistent
python tests\check_self_description.py
#   expected: problems found: 0
#   note: a new category must also be added to the allow-list in tests\check_self_description.py

# 3) packaging metadata is consistent
python check_install.py --quick
#   expected: py-modules  N declared, all present
#         top-level modules  all declared in pyproject.toml

# 4) protocol compliance
python tests\check_mcp_compliance.py
#   expected: 17/17 passed

# 5) real functional verification (needs CST)
#    first without solving: the preview is offline, then the geometry must really change
python tests\verify_sweep_geometry.py
#    then with solves, on a PEC-only base so the rebuild cannot depend on a library material
python tests\verify_sweep_solve.py
#   expected: the case counts for the three modes are correct; over max_cases is rejected;
#             the geometry changes per case; the small sweep completes
```

**Always call `cst_quit_tool` at the end** — every open project holds about 700 MB, and
not releasing them accumulates until memory is exhausted, with the next solve reporting `Not enough memory`.

---

## 7. Extending into other functionality

| What you want to add | Where it goes |
|---|---|
| a new modelling primitive or operation | `cst_mcp/vba/geometry.py` (generates VBA) + `cst_mcp/tools/geometry_tools.py` (registration) |
| a new solver / monitor / boundary option | `cst_mcp/tools/simulation_tools.py` |
| a new result readout or check | `cst_mcp/tools/result_tools.py` |
| a material or port capability | `cst_mcp/tools/material_port_tools.py` |
| a project / session behaviour | `cst_mcp/tools/session_tools.py` |
| **a whole new domain (like the sweep)** | **create `cst_mcp/tools/<family>_tools.py`, with the helper logic at the top level** |

The CST-facing mechanics all live in `cst_mcp/session.py` (VBA execution, the Design Environment, project open/save,
message reading), the guards in `cst_mcp/lint.py`, and the registration machinery in `cst_mcp/registry.py`.

**When you are done, do not forget to tell me (or your future self) three things**: the tool name, which CST command
it corresponds to (`replaces_vba`), and what **non-obvious preconditions** it has (written into `notes`).

---

## Related documents

* [Extending the CST MCP](overview.md) — the condensed view of the registration mechanism and the registry API
* [Layout](../dev/layout.md) — the full repository map the new files sit in
* [Tool catalogue](../use/tool-catalogue.md) — the categories and tools a new family joins
* [Failures hit during development](../../tests/evidence/known_failures.md) — raw CST errors behind the traps in section 5
* [AGENTS.md](../../AGENTS.md) — the mandatory rules for a change made by an agent
