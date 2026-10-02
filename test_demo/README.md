# test_demo

A self-contained CST project used to verify that the MCP is installed **and can actually
drive CST** — not merely that it imports.

| | |
| --- | --- |
| File | `test_demo.cst`, 22 KB |
| Contains | a project scaffold; the verification task builds the model itself |
| Companion directory | not required — the model is stored inside the single file |
| Machine-specific content | none |

## How to use it

Hand the ready-to-paste prompt in
[Verify with the demo project](../docs/start/verify-with-demo.md) to your AI. It installs
the MCP and the two skills, then builds a 50 mm cube, a PEC sheet 2 mm below it, a discrete
port between the two, sets 0–100 MHz and solves.

What a pass looks like — and the two traps worth knowing — is on that page.

> **Open a copy** if you want to keep this file pristine. CST writes a companion directory
> next to the `.cst` once a project is opened and saved; that directory is git-ignored, and
> the committed file is self-contained without it.

---

## Related documents

* [Verify with the demo project](../docs/start/verify-with-demo.md) — the prompt, the pass criteria and the traps
* [Installation](../docs/start/install.md) — the install this demo verifies
* [Quick start](../docs/use/quickstart.md) — the first tool call, without a demo project
* [Layout](../docs/dev/layout.md) — where this folder sits in the repository
