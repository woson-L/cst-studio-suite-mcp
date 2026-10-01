# Extending the CST MCP

The tool surface is designed to grow. Adding a capability means adding **one
module** — no edits to the server plumbing, no edits to the manifest, no changes
to how tools are registered with MCP.

---

## 1. How registration works

```
mcp_server.py
  ├── creates ToolRegistry()
  ├── registry.discover_extensions("cst_mcp.tools")   # imports every module in cst_mcp/tools/
  │      └── each module's register_tools(registry) is called
  ├── for spec in registry.all(): mcp.add_tool(spec.handler, name=..., description=...)
  └── build_manifest()                                # generated from the same registry
```

Because the manifest is generated from the registry, the documentation can never
drift from the implementation. A tool that is not in the registry does not exist
to MCP either.

---

## 2. Add a tool

Create `cst_mcp/tools/my_feature.py`:

```python
"""Short description of the feature."""
from __future__ import annotations

from typing import Any

from ..registry import ToolRegistry
from ..session import session

CATEGORY = "myfeature"          # becomes a manifest category


def register_tools(registry: ToolRegistry) -> None:
    s = session                  # the shared CSTSession

    @registry.tool(
        "cst_my_operation_tool",                 # must start with cst_
        "One sentence saying what it does.",     # shown to the agent
        CATEGORY,
        params={"solid": "str", "value": "float", "optional_flag": "bool"},
        required=["solid", "value"],
        returns="{ok, applied}",
        examples=[{"solid": "board:ground", "value": 1.5}],
        notes=["Anything the caller must know to use it correctly."],
        replaces_vba="TheCstObject.TheMethod",
    )
    def my_operation(solid: str, value: float, optional_flag: bool = False) -> dict[str, Any]:
        code = f'Solid.ChangeMaterial "{solid}", "PEC"\n'
        return {**s().add_history(f"my operation on {solid}", code),
                "value": value, "flag": optional_flag}
```

Restart the MCP server. The tool is now callable, appears in
`cst_list_mcp_tools_tool`, and is written into `docs/mcp_tools.json` by
`cst_tool_manifest_tool`.

### Parameter hints

`params` maps a parameter name to a short type hint, which is converted into a
JSON-schema fragment for MCP:

| hint | schema |
| --- | --- |
| `"str"` | `{"type": "string"}` |
| `"int"` | `{"type": "integer"}` |
| `"float"` | `{"type": "number"}` |
| `"bool"` | `{"type": "boolean"}` |
| `"dict"` | `{"type": "object"}` |
| `"list"` | `{"type": "array"}` |
| `"str | null"` | `{"type": ["string", "null"]}` |

Anything listed in `required` is added to the schema's `required` array, so the
MCP client rejects bad calls before your handler runs.

### Registry API

```python
registry.tool(name, summary, category, *, params, required, returns,
              examples, notes, replaces_vba)      # decorator
registry.add(name, summary, category, handler, ...)  # imperative form
registry.get(name)      # ToolSpec, raises KeyError with the available names
registry.all()          # sorted ToolSpec list
registry.by_category()  # {category: [ToolSpec, ...]}
registry.names()
len(registry), name in registry
```

---

## 3. Practical rules for new tools

1. **One responsibility per tool.** A tool that both models and solves is hard
   for an agent to sequence and hard to retry.
2. **Return a dict.** MCP surfaces it as structured content; agents parse it.
   Do not return a bare string.
3. **Return the read-back value.** After changing something, read it back from
   CST and put the observed value in the result. This is the difference between
   "the call succeeded" and "the change took effect".
4. **Never put `StoreParameter`/`StoreParameters`/`Rebuild` in a history block.**
   The session layer lints for those tokens and raises `HistoryBlockRejected`.
   If you need parameters, call `session().set_parameters()` or
   `session().ensure_parameters()`.
5. **Validate before CST sees it.** Reject unknown enum values, out-of-range
   numbers and structurally impossible geometry (for example a cone with both
   radii zero) in the tool. A clear Python error is cheaper than a CST message.
6. **Use the session helpers**: `run_vba` (immediate), `add_history` (recorded),
   `messages` / `error_messages` (diagnostics), `parameter` / `list_parameters`.
7. **Set `replaces_vba`** to the CST command you wrap. It documents intent and
   makes the mapping searchable.

---

## 4. Where each kind of change belongs

| You want to … | Put it in |
| --- | --- |
| add a modelling primitive or operation | `cst_mcp/vba/geometry.py` (builder) + `cst_mcp/tools/geometry_tools.py` (tool) |
| add a solver, monitor or boundary option | `cst_mcp/tools/simulation_tools.py` |
| add a result or verification readout | `cst_mcp/tools/result_tools.py` |
| add a material or port capability | `cst_mcp/tools/material_port_tools.py` |
| add a project/session behaviour | `cst_mcp/tools/session_tools.py` |
| add a new domain entirely | a new `cst_mcp/tools/<name>_tools.py` module |

`cst_mcp/session.py` holds CST-facing mechanics (VBA execution, the Design
Environment, project save/open, message reading). `cst_mcp/lint.py` holds the
guards. `cst_mcp/registry.py` holds the registration machinery.

---

## 5. Testing a new tool

Offline (no CST needed) — proves the tool registers and the manifest is valid:

```powershell
python tests\smoke_registry.py
```

Against a live CST — exercises the whole chain:

```powershell
python tests\verify_live.py
```

Protocol-level checks (MCP handshake, schemas, error semantics):

```powershell
python tests\check_mcp_compliance.py
```

Both runners write a JSONL progress file, so a hang never loses the log.

---

## 6. Adding a whole command family (the vendored CLI case)

The shipped `vendor/cst-runtime-cli` turned out to be missing its
`scripts/cst_runtime/` package, which made the seven `cst_runtime_*` /
`cst_toolbox_*` tools fail with `cst-runtime-cli scripts not found`. Those tools
are now served by a built-in command registry in
`cst_runtime_cli_bridge.py`:

```python
COMMANDS = {
    "inspect-project": {
        "handler": _cmd_inspect_project,
        "category": "engineering",
        "summary": "...",
        "args": {...},
    },
    ...
}
```

To add a command to that family, add one entry to `COMMANDS` with a handler that
returns a dict. It is then reachable through `cst_runtime_invoke_tool`,
listed by `cst_runtime_list_tools_tool`, and described by
`cst_runtime_describe_tool` — again with no other file to touch.

If a complete `scripts/cst_runtime/` ever becomes available, drop it at
`vendor/cst-runtime-cli/skills/cst-runtime-cli/scripts` and restore the original
subprocess-based bridge; the public function names are unchanged.

---

## 7. Worked example: the parameter-sweep family

The sweep tools are the reference for adding a **family** rather than a single tool,
and every trap below was hit for real while building it. Read this before adding a
similar multi-step capability.

### The five files and why each exists

| File | Role | Auto-discovered? |
| --- | --- | --- |
| `cst_mcp/tools/sweep_tools.py` | registers the two tools; the only file that talks to the registry | **yes** — scanned from `cst_mcp.tools` |
| `cst_parameter_sweep.py` | case enumeration (pure Python) + the per-case runner | no |
| `cst_automation.py` | the CST session manager the runner drives | no |
| `cst_schematic.py` | VBA helpers `cst_automation` imports | no |
| `pyproject.toml` | must list all three top-level modules | — |

The split is deliberate: enumerating cases needs no CST at all, so
`cst_sweep_preview_tool` can answer on a machine where CST is not installed.

### Trap 1 — a top-level module that is not declared vanishes from an installed wheel

Only `cst_mcp/tools/*.py` is auto-discovered. A top-level helper runs fine from the
source folder and then disappears once the package is installed, because it was never
part of the distribution. Add every top-level module to `[tool.setuptools] py-modules`
in `pyproject.toml`. `check_install.py` fails the build check if the list and the files
on disk disagree.

### Trap 2 — `.env` is not loaded for you

`cst_mcp.config.load_env()` populates `os.environ` from `.env`, and the core tools get
that because importing `cst_mcp` triggers it. A top-level module that reads
`os.environ["CST_INSTALL_ROOT"]` directly does **not**. Call `config.load_env()`
yourself before using such a module:

```python
def _manager():
    config.load_env()                      # <- without this, CST_INSTALL_ROOT is unset
    from cst_automation import CSTSessionManager
    return CSTSessionManager()
```

### Trap 3 — `CSTSessionManager.connect()` never launches CST

It only attaches to something already running. With no Design Environment up, every
case failed with:

```
RuntimeError: No DEs found to connect to.
```

Attach if you can, launch only if you must, so an existing CST with open projects is
reused rather than duplicated:

```python
manager = CSTSessionManager()
try:
    manager.connect(launch_if_needed=False)
except Exception:
    manager.connect(launch_if_needed=True)
```

### Trap 4 — a parameter change must run through `execute_vba`, **not** `add_to_history`

This one fails in two different ways depending on how you wrap it, both verified live:

| Attempt | CST answer |
| --- | --- |
| bare block into `add_to_history` | `The rebuild operation cannot be used inside a structure macro.` / `Prevented attempt to change the value for parameter X inside history rebuild` — and the Design Environment can be left unresponsive |
| `Sub Main` block into `add_to_history` | `Unterminated block ... in add_to_history` — `add_to_history` wants a history block, not a macro |
| bare block into `execute_vba` | **works** — `execute_vba` adds the `Sub Main` wrapper and calls `_execute_vba_code` |

So: **build a bare VBA block, hand it to `execute_vba()`.** That is the same channel
`cst_mcp.session.set_parameters()` uses, and the same rule stated in section 3.4.

### Trap 5 — a library material does not survive save/reopen

Discovered while testing the sweep, and it invalidates the obvious design:

```
MaterialLibrary.LoadMaterialFromLibrary ("Iron", "", True)
```

loading a material does **not** persist into the saved `.cst`. Reopening the project
and rebuilding fails at the solid that uses it:

```
(&H8000ffff) The specified material does not exist: Iron
(.Create)
```

A rebuild is intrinsic to changing a parameter, so **a sweep over a project that uses a
library material cannot rebuild its cases.** Observed behaviour of the two halves:

* the parameter value *is* written (`StoreParameters` alone succeeds and reads back);
* the geometry does **not** follow, because the rebuild cannot replay the history that
  created the solid.

Consequences for anyone extending this:

* prefer **materials defined in the project** (`cst_create_material_tool`) over
  library-loaded ones if the model has to be rebuilt in a later session;
* verify a project rebuilds **after being reopened** before sweeping it — that, not the
  sweep code, is the usual reason all cases fail;
* if a case must change a parameter, do not assume success from `StoreParameters`
  alone: read the value back **and** confirm the geometry moved.

### The tool definitions, stripped down

```python
CATEGORY = "sweep"

def register_tools(registry: ToolRegistry) -> None:
    @registry.tool(
        "cst_sweep_preview_tool",
        "Expand a parameter sweep spec into concrete cases and report the case count. Does not start CST.",
        CATEGORY,
        params={"parameters": "dict", "mode": "str", "max_cases": "int"},
        required=["parameters"],
        returns="{ok, mode, case_count, parameters, cases}",
        examples=[{"parameters": {"L": "48:52:2"}, "mode": "single"}],
        notes=["Call this BEFORE cst_sweep_run_tool ..."],
        replaces_vba="(no CST VBA - pure case enumeration)",
    )
    def sweep_preview(parameters: dict, mode: str = "cartesian",
                      max_cases: int = 200) -> dict[str, Any]:
        from cst_parameter_sweep import preview_sweep   # imported inside: optional family
        return preview_sweep(parameters=parameters, mode=mode, max_cases=max_cases)
```

Two conventions worth copying:

* **import inside the handler.** If the optional helper modules are missing, every
  other tool still works; only this family reports the problem.
* **split cheap from expensive.** A preview that never opens CST can be called freely,
  and it is what turns "sweep L and w" into a number the user can approve.

### Verifying a family like this

```powershell
python tests\smoke_registry.py            # the tools register; no duplicate names
python tests\check_self_description.py    # category is allowed; examples bind
python tests\verify_sweep_geometry.py     # live CST: the geometry really changes per case
python tests\verify_sweep_solve.py        # live CST: the same sweep, with solves
```

`verify_sweep_geometry.py` is the model to copy for the cheap half: it asserts the
preview works **without** CST, guards `max_cases`, and then checks that the geometry
actually changed per case — not merely that the parameter value was written. That
distinction is what made an earlier library-material run misleading.
`verify_sweep_solve.py` adds the solves, on a deliberately simple PEC-only base so the
rebuild cannot depend on a library material.

---

## Related documents

* [Adding a tool family by hand](add-a-tool-family.md) — the step-by-step manual for a whole family, including the traps hit in live testing
* [Layout](../dev/layout.md) — where each module, tool category and helper file lives
* [Rules that keep results trustworthy](../use/rules.md) — the operating rules a new tool must not break
* [Verification](../dev/verification.md) — the checks that prove a change works, offline and against CST
* [Contributing](../../CONTRIBUTING.md) — what to run, and what to discuss first, before a pull request
