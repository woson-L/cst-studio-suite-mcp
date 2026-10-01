# Known limits

> **Documentation index** › Known limits


* Parameter values are passed as CST expressions; a value containing a comma is
  rejected as a likely list.
* Overwriting a project path closes any project still open on it: a CST project keeps
  its `Model/` and `Result/` files locked while it is open, and the save otherwise
  fails with a bare `Failed to save project`. Asking for that path to be replaced
  implies closing it.
* Remote/MPI/distributed solving and optimisation loops are not wrapped as tools
  (the runtime bridge can still `invoke` what exists).
* `vendor/cst-runtime-cli` is missing its `scripts/cst_runtime/` package in the
  shipped tree, so the seven `cst_runtime_*` / `cst_toolbox_*` tools are served
  by a built-in command registry instead of the original CLI. The public tool
  names and arguments are unchanged.

---

## Related documents

* [What CST 2026.2 does not expose](cst-2026-limits.md) — the other half of the limits, in CST itself
* [Rules that keep results trustworthy](rules.md) — how to work within them
* [Tool catalogue](tool-catalogue.md) — the tools that are wrapped, by category
* [Extending the tool surface](../extend/overview.md) — adding what is missing
* [Verification](../dev/verification.md) — what the shipped tree was checked with
