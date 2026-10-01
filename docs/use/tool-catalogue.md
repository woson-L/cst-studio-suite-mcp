# Tool catalogue

> **Documentation index** › Tool catalogue


| Category | Tools | Purpose |
| --- | --- | --- |
| `session` | 14 | health, detect, connect, project create/open/save/close, messages, raw VBA, history blocks, release |
| `parameters` | 4 | read, create, change, delete design parameters |
| `geometry` | 14 | brick, cylinder, sphere, cone, torus, ECylinder, bondwire, boolean, transform, extrude, component |
| `material` | 3 | create, assign, load from library (with rename) |
| `port` | 3 | discrete port, waveguide port, list ports |
| `solver` | 11 | solver choice, frequency range (unit-aware), FD/TD/eigenmode configuration, boundary, symmetry, background, run |
| `mesh` | 2 | mesh type and density (incl. `smallest_feature_mm`). No mesh-generation tool — see above |
| `monitor` | 2 | add and list field monitors |
| `results` | 2 | list result tree, read a 1D item |
| `verify` | 5 | S11, reference impedance, port info (with verdict), energy budget, model audit |
| `export` | 3 | Touchstone, ASCII, summary JSON |
| `sweep` | 2 | parameter sweep: preview the case count, then run it case by case |
| `runtime` | 16 | built-in command bridge + typed wrapper generation |
| `meta` | 3 | list tools, full manifest, dynamic dispatch |

**84 tools across these 14 categories.** `cst_list_mcp_tools_tool` prints the live
list; `cst_tool_manifest_tool` writes the full JSON.

---

## Related documents

* [What it looks like in use](usage.md) — these tools in a working session order
* [Rules that keep results trustworthy](rules.md) — the conditions several of these tools enforce
* [What CST 2026.2 does not expose](cst-2026-limits.md) — why some expected tools do not exist
* [Extending the tool surface](../extend/overview.md) — how a new tool is registered and tested
* [Tool manifest](../mcp_tools.json) — the same tools as machine-readable JSON
