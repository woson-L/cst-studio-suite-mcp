# Quick start

> **Documentation index** › Quick start


### 1. Point it at your CST

```powershell
Copy-Item .env.example .env
notepad .env
```

```ini
CST_INSTALL_ROOT=C:\Program Files\CST Studio Suite 2026
CST_DESIGN_ENVIRONMENT_EXE=C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe
CST_MCP_WORKSPACE=C:\CST_MCP_workspace
CST_MCP_EVIDENCE=C:\CST_MCP_workspace\evidence
```

`CST_MCP_WORKSPACE` is where projects created through the MCP are saved. CST
otherwise keeps a new project in a Temp folder that disappears between calls —
a common cause of `There is no active CST project currently.`

### Copying this folder to another computer

Only the paths in `.env` are machine-specific — the code, the tools and the
manifest are drive-independent. After copying the folder (say to `C:\CST-MCP`):

```powershell
Set-Location "C:\CST-MCP"
Copy-Item .env.example .env
notepad .env        # set CST_INSTALL_ROOT, CST_DESIGN_ENVIRONMENT_EXE,
                    # CST_MCP_WORKSPACE, CST_MCP_EVIDENCE for that machine
```

Then check that everything resolves on the new machine:

```powershell
python check_install.py --quick     # files, .env paths, registry — no CST needed
python check_install.py             # adds an MCP handshake and a live CST check
```

`python check_install.py --fix` can look for the CST installation on this machine
and write the two CST keys into `.env` for you; `--list-installs` shows what it
would choose without changing anything. It deliberately leaves an existing
`CST_MCP_WORKSPACE` alone.

One more path matters: **the Python that runs the server**. A `.venv` created
inside this folder keeps working after the copy only if the base Python lives at
the same location on the new machine. The reliable options are the Python bundled
with CST, or any Python 3.10+ that has `mcp` installed — the server only needs to
be able to `import mcp` and read `mcp_server.py`.

> The full, task-oriented walkthrough for a fresh machine — including where to
> point your MCP client and how to verify each stage — is in
> [`start/install.md`](../start/install.md).

### 2. Install the dependencies

The server needs Python 3.10+ with the `mcp` package. If you already have a
working virtual environment next to the CST MCP (for example
`...\cst-studio-suite\.venv`), it can run the server directly:

```powershell
& "C:\CST-MCP\.venv\Scripts\python.exe" -c "import mcp; print('mcp ok')"
```

Otherwise create one:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

### 3. Run it

```powershell
.\.venv\Scripts\python.exe mcp_server.py
```

It speaks MCP over stdio, so normally your MCP client starts it. A client entry
looks like this (Codex / Claude style):

```toml
[mcp_servers.cst-studio-suite]
command = "C:\\CST-MCP\\.venv\\Scripts\\python.exe"
args = ["C:\\CST-MCP\\mcp_server.py"]
cwd = "C:\\CST-MCP"
```

or in the DSH harness patch layer:

```yaml
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

### 4. First call

```
cst_health_check_tool {}
```

Expect `ready: true`, `cst_interface_importable: true`,
`cst_results_importable: true`, `workspace_writable: true`.

---

## Related documents

* [What it looks like in use](usage.md) — a complete session, call by call
* [Tool catalogue](tool-catalogue.md) — every tool grouped by category
* [Install on a fresh machine](../start/install.md) — the longer walkthrough this page compresses
* [Verification](../dev/verification.md) — what `check_install.py` proves about an installation
* [Known limits](known-limits.md) — what this server deliberately does not do
