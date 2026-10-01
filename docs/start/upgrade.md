# Installing over an existing installation

> **Documentation index** › Installing over an existing installation


Replace the old folder with this one, then bring back the two things it holds
that this package does not ship:

```powershell
Move-Item "<old mcp folder>" "<old mcp folder>_backup"
Move-Item "C:\CST-MCP" "<old mcp folder>"
Copy-Item "<old mcp folder>_backup\.venv" "<old mcp folder>\.venv" -Recurse   # the working Python
Copy-Item "<old mcp folder>_backup\.env"  "<old mcp folder>\.env"  -Force     # if it exists
```

The old `vendor\` and `examples\` folders are optional: the seven
`cst_runtime_*` / `cst_toolbox_*` tools are served by a built-in command registry,
so nothing has to be carried over. Copy `vendor\` only if you want the
cst-runtime-cli references on hand.

Then confirm the installation:

```powershell
Set-Location "<old mcp folder>"
python check_install.py
```

The script fails loudly when `CST_INSTALL_ROOT` or `CST_DESIGN_ENVIRONMENT_EXE`
names a folder that does not exist on the machine — the usual cause of a server
that starts but cannot reach CST after an installation is moved between
computers. `CST_INSTALL_ROOT` is the value to re-check first, because the old one
usually names a different drive.

Python is used rather than PowerShell on purpose: it needs no execution-policy
change and behaves the same on every machine.

---

## Related documents

* [Verification](../dev/verification.md) — what `check_install.py` checks and what it proves
* [Install on a fresh machine](install.md) — the from-scratch path this one skips
* [Quick start](../use/quickstart.md) — first run after the folder has moved
* [Repository layout](../dev/layout.md) — what the package ships and what has to be carried over
* [Known limits](../use/known-limits.md) — why the built-in runtime registry is enough
