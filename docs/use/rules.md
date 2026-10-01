# Rules that keep results trustworthy

> **Documentation index** › Rules that keep results trustworthy


Read `skills/cst-studio-suite-mcp/SKILL.md` for the detail. The short version:

1. **Change parameters only with `cst_set_parameters_tool`.** Writing
   `StoreParameter`/`Rebuild` into a history block is refused by CST, and in
   testing it left the Design Environment permanently unresponsive. The server
   rejects such blocks before they reach CST.
2. **Save before solving**, and set the frequency range first — otherwise
   `Solver run failed. Frequency range not set correctly.`
3. **Verify the port after every solve.** A solver reports success even when the
   port mode is evanescent: a real case had a 51.9 GHz cutoff and a 7623 Ω
   reference on a 2.4 GHz microstrip port, giving a flat −0.6 dB S11 that looks
   plausible and is meaningless.
4. **Quote numbers from exported files**, not from the screen.
   `S11_dB = 20*log10(abs(S11))`; never call `Abs(E)` a gain.

---

## Related documents

* [What CST 2026.2 does not expose](cst-2026-limits.md) — the API limits behind these rules
* [Known limits](known-limits.md) — what this server accepts and refuses
* [Verification](../dev/verification.md) — the runs that back each claim
* [Known failures](../../tests/evidence/known_failures.md) — the raw CST errors and the conclusions drawn
* [Tool catalogue](tool-catalogue.md) — the tools these rules name
