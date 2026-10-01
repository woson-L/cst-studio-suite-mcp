# Summary

<!-- What changes, and why. One concern per pull request. -->

## Evidence

<!--
This project accepts a claim about CST behaviour only when it was measured.
Delete whichever lines do not apply.
-->

- CST Studio Suite version tested: `2026.2`
- Before this change, the exact behaviour/message was:
  ```
  <paste the raw CST text>
  ```
- After this change:
  ```
  <paste the raw CST text>
  ```

## Checks

<!-- Paste the tail of each run. All must be 0 problems and exit 0. -->

- [ ] `python check_install.py --quick`
- [ ] `python tests/smoke_registry.py` (regenerates `docs/mcp_tools.json` if the tool surface changed)
- [ ] `python tests/check_mcp_compliance.py`
- [ ] `python tests/check_self_description.py`
- [ ] `python tests/check_skill_tool_refs.py`
- [ ] `python tests/check_skill_layout.py`
- [ ] `python tests/check_docs_consistency.py`
- [ ] `python tests/test_audit_regressions.py`
- [ ] `python tests/test_port_info_verdict.py`
- [ ] `python tests/test_save_overwrite.py`
- [ ] Live runners, if this touches the CST bridge: `tests/verify_fixes_live.py`

## Documentation

<!-- AGENTS.md makes this part of the change, not a follow-up. -->

- Documents updated in this pull request:
- Documents intentionally **not** updated, and why:

## Notes for the reviewer

<!-- Optional: anything you were unsure about, or a decision you would like a second opinion on. -->
