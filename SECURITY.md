# Security Policy

## Reporting a vulnerability

Report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/woson-L/cst-studio-suite-mcp/security/advisories/new)
rather than in a public issue.

Please include: what you did, what happened, what you expected, and the versions
involved (`python --version`, the CST Studio Suite build, and the commit you tested).
Expect an initial reply within a few days. This is a small project maintained on a
best-effort basis; there is no bug bounty.

## What counts as a vulnerability here

The server runs locally, speaks MCP over **stdio**, and makes **no network requests**.
The realistic attack surface is therefore narrow, but these are real:

| Class | Example |
| --- | --- |
| Code execution through generated VBA | A tool argument that escapes its quoting and becomes a second VBA statement |
| Path traversal / unintended file writes | A tool argument that writes outside `CST_MCP_WORKSPACE` and `CST_MCP_EVIDENCE` |
| Secrets in logs or evidence files | A credential or licence string written into `tests/evidence/` |

Two guards already exist and should not be weakened: parameter **names** are validated as
plain identifiers before they are interpolated into a `StoreParameters` block, and history
blocks are linted for `StoreParameter` / `Rebuild` before they reach CST
(`cst_mcp/lint.py`). A bypass of either is a security report, not a bug report.

## Out of scope

- Anything that requires the attacker to already control the `.env` file, the MCP client,
  or the local account running CST.
- CST Studio Suite itself — report those to Dassault Systèmes. This project only calls
  the automation API that CST ships.
- Denial of service through genuinely expensive simulations; the memory guard already
  refuses to start a solve on a low-memory machine and `allow_low_memory: true` is a
  deliberate opt-out.

## Handling of credentials

This repository must never contain credentials. `.env` is git-ignored and `.env.example`
holds placeholders only. If you find a committed secret, report it privately — it will be
rotated and the history rewritten.
