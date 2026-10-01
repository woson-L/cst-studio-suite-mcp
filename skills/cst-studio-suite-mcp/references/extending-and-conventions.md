# Extending the server

Adding a tool never means editing the server plumbing.

1. Create `cst_mcp/tools/<your_module>.py`.
2. Define `register_tools(registry)` and register with `registry.tool(...)` (or
   `registry.add(...)`).
3. Restart the MCP server. `cst_mcp.tools` is scanned at start-up and every module
   exposing the hook is loaded.

```python
from ..registry import ToolRegistry
from ..session import session

CATEGORY = "custom"

def register_tools(registry: ToolRegistry) -> None:
    @registry.tool(
        "cst_my_tool", "One-line summary.", CATEGORY,
        params={"solid": "str", "value": "float"},
        required=["solid"],
        examples=[{"solid": "board:ground", "value": 1.0}],
        replaces_vba="TheCstObject.TheMethod",
    )
    def my_tool(solid: str, value: float) -> dict:
        return session().add_history("my block", f'Solid.ChangeMaterial "{solid}", "PEC"')
```

The new tool appears in `cst_list_mcp_tools_tool` and in the generated manifest
automatically. See `docs/extend/overview.md` for the full contract, including the
manifest fields and the `params` type hints.

## Conventions that keep a new tool consistent

* **Name** it `cst_<verb>_<object>_tool`. The docs gate
  (`tests/check_docs_consistency.py`) enforces the pattern and will reject a documented
  tool name that does not exist.
* **Declare `params` for every parameter** and list the truly required ones in
  `required`. Every example must bind: the offline gates execute the examples against a
  stub session and fail on an undeclared key.
* **Delete `notes` that lie.** A doc/code mismatch is a real defect: the notes are what
  the model reads to choose values. If the implementation rejects a value, the notes
  must not advertise it.
* **Do not invent CST method names.** Record a macro in CST, paste the VBA, then replace
  the numbers with parameter names — that is how every method name in this package was
  obtained. Names that look right but do **not** exist in 2026.2 include
  `MaterialUnit`, `Color`, `LoadFromLibrary`, `Solver.GetFrequencyRange(i)`,
  `Monitor.GetName(i)`, `ASCIIExport.SetSubset`, `Solver.MeshType`, `Solver.Reset`,
  `Mesh.Create`, `Mesh.Reset`, and the bare `Mesh` statement.
* **Prefer settings over actions.** Where CST only offers settings (the `Mesh` object),
  do not wrap a non-existent action around them.
* **Fail loudly on values CST would reject.** Emitting nothing while reporting success
  is the worst outcome — it produced two of the bugs recorded in
  `tests/evidence/known_failures.md`.
* **Late-bind the session.** Use a module-level `_sess = session` alias and, inside
  `register_tools`, `s = lambda *a, **k: _sess(*a, **k)`. Binding `s = session` at
  import time freezes the factory so the module cannot be tested with a stub.
* **Register a check.** Add the tool's behaviour to `tests/test_audit_regressions.py`
  (offline, stub session) and, if it touches CST, to `tests/verify_fixes_live.py`
  (live). A tool with no test is a tool that will regress silently.

---

## Related documents

* [Extending the CST MCP](../../../docs/extend/overview.md) — the full registration contract and manifest fields
* [Adding a tool family](../../../docs/extend/add-a-tool-family.md) — a standalone manual for adding a whole family
* [Verification](../../../docs/dev/verification.md) — the checks a new tool must pass
* [Tool catalogue and call order](tool-catalogue-and-order.md) — the layer a new tool joins
