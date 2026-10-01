"""Regression tests for the port-info verdict threshold.

The original verdict compared the cutoff frequency against a hardcoded 2.0 GHz:

    "OK: cutoff is below the operating band" if cutoff < 2.0 else "WARNING: ..."

That is only correct for a ~2.4 GHz project. It falsely cleared an evanescent
port in any band above 2 GHz and falsely warned on a perfectly good millimetre
wave port. These tests pin the corrected behaviour: compare against the actual
operating frequency, never a magic constant.

No CST connection is made - the session object is replaced by a stub.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cst_mcp.tools import result_tools  # noqa: E402

import mcp_server  # noqa: E402,F401  - importing it runs bootstrap(), which loads the tools


class FakeSession:
    """Stands in for the CST session; only the two methods read_port_info uses."""

    def __init__(self, cutoff: float | None):
        self.cutoff = cutoff

    def read_result(self, path, cst_file=None, max_points=None):  # noqa: ARG002
        if "Cutoff Frequency" in path:
            if self.cutoff is None:
                raise RuntimeError("tree item does not exist")
            return {"data": [[2.4, self.cutoff]]}
        raise RuntimeError("tree item does not exist")

    def messages(self, limit=15):  # noqa: ARG002
        return []


def _handler():
    return mcp_server.registry.get("cst_read_port_info_tool").handler


#: The genuine implementation, captured before any test replaces it.
_REAL_SOLVER_BAND = result_tools._solver_band


def run_case(label: str, cutoff, operating, expected, *, ban_magic=True):
    result_tools._sess = lambda: FakeSession(cutoff)  # type: ignore[assignment]
    out = _handler()(operating_frequency=operating)
    verdict = str(out.get("verdict", ""))
    ok = expected.lower() in verdict.lower()
    if ban_magic:
        # the old failure mode: a magic 2.0 threshold must not decide the verdict
        if cutoff is not None and operating is not None and cutoff < 2.0 <= operating:
            ok = False  # would wrongly read OK for a port evanescent at 77/94 GHz
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}")
    print(f"        cutoff={cutoff}  operating={operating}")
    print(f"        verdict: {verdict[:150]}")
    return ok


def main() -> int:
    results = []

    # --- the original verified defect: evanescent 51.95 GHz cutoff at 2.4 GHz ----
    results.append(run_case("evanescent port at 2.4 GHz must warn",
                            51.95, 2.4, "WARNING"))

    # --- the bug the fix is really about: high-band ports above the magic 2.0 GHz --
    # A 77 GHz radar port with 30 GHz cutoff is perfectly propagating. The old
    # `cutoff < 2.0` test labelled it WARNING (false alarm); it must read OK.
    results.append(run_case("propagating 77 GHz radar port must read OK",
                            30.0, 77.0, "OK"))

    # And an evanescent port above 2 GHz must NOT be cleared, which the old test did.
    results.append(run_case("evanescent port at 77 GHz must warn",
                            90.0, 77.0, "WARNING"))

    # --- low band: 433 MHz module, cutoff below the band --------------------------
    results.append(run_case("propagating 433 MHz port must read OK",
                            0.3, 0.433, "OK"))

    # --- discrete port: no port-mode tree item -----------------------------------
    results.append(run_case("discrete port has no cutoff information",
                            None, 2.4, "no port mode information"))

    # --- no reference and no readable band: must say UNKNOWN, not OK --------------
    result_tools._sess = lambda: FakeSession(51.95)  # type: ignore[assignment]
    result_tools._solver_band = lambda: None  # type: ignore[assignment]
    out = _handler()(operating_frequency=None)
    unknown = "UNKNOWN" in str(out.get("verdict", ""))
    print(f"[{'PASS' if unknown else 'FAIL'}] no reference frequency -> UNKNOWN, never OK")
    print(f"        verdict: {str(out.get('verdict'))[:150]}")
    results.append(unknown)

    # --- the project's own band is used when the caller gives no frequency --------
    # 51.95 GHz cutoff inside a 2.2-2.7 GHz band: the fallback must pick up 2.2 and
    # warn. This case is exactly what the old `cutoff < 2.0` test also happened to
    # get right for 2.4 GHz projects, which is why the bug stayed hidden.
    result_tools._solver_band = lambda: (2.2, 2.7)  # type: ignore[assignment]
    out = _handler()(operating_frequency=None)
    used_band = (out.get("reference_frequency") == 2.2
                 and "solver lower band edge" in str(out.get("reference_source", ""))
                 and "WARNING" in str(out.get("verdict", "")))
    print(f"[{'PASS' if used_band else 'FAIL'}] falls back to the project's own solver band")
    print(f"        reference={out.get('reference_frequency')} "
          f"source={out.get('reference_source')}")
    print(f"        verdict: {str(out.get('verdict'))[:150]}")
    results.append(used_band)

    # --- the project band clears a port that is genuinely fine ---------------------
    result_tools._solver_band = lambda: (70.0, 80.0)  # type: ignore[assignment]
    out = _handler()(operating_frequency=None)
    cleared = (out.get("reference_frequency") == 70.0
               and "OK" in str(out.get("verdict", "")))
    print(f"[{'PASS' if cleared else 'FAIL'}] project band of 70-80 GHz clears a 30 GHz cutoff")
    print(f"        reference={out.get('reference_frequency')}  "
          f"verdict: {str(out.get('verdict'))[:120]}")
    results.append(cleared)

    # --- _solver_band itself: real VBA path against a stub message window ----------
    # Restore the genuine implementation: earlier cases replaced it with a lambda.
    result_tools._solver_band = _REAL_SOLVER_BAND  # type: ignore[assignment]

    class BandSession:
        """Reports a solver band the way the real VBA bridge does: via the message window."""

        def run_vba(self, code):
            self.code = code

        def messages(self, limit=15):  # noqa: ARG002
            return [{"type": "Information", "text": "MCPPORTBAND=2.2|2.7"}]

    result_tools._sess = lambda: BandSession()  # type: ignore[assignment]
    band = result_tools._solver_band()
    parsed = band == (2.2, 2.7)
    print(f"[{'PASS' if parsed else 'FAIL'}] _solver_band parses the message-window payload")
    print(f"        parsed: {band}")
    results.append(parsed)

    # --- and it must return None, not raise, when the window has nothing -----------
    class EmptySession(BandSession):
        def messages(self, limit=15):  # noqa: ARG002
            return [{"type": "Information", "text": "unrelated chatter"}]

    result_tools._sess = lambda: EmptySession()  # type: ignore[assignment]
    quiet = result_tools._solver_band() is None
    print(f"[{'PASS' if quiet else 'FAIL'}] _solver_band returns None when the marker is absent")
    results.append(quiet)

    # --- a dead session must not raise out of the helper ---------------------------
    class DeadSession:
        def run_vba(self, code):  # noqa: ARG002
            raise RuntimeError("no active CST project")

        def messages(self, limit=15):  # noqa: ARG002
            return []

    result_tools._sess = lambda: DeadSession()  # type: ignore[assignment]
    survived = result_tools._solver_band() is None
    print(f"[{'PASS' if survived else 'FAIL'}] _solver_band swallows a dead-session error")
    results.append(survived)

    # --- a band-read failure must not block an explicit operating frequency -------
    def _boom():
        raise RuntimeError("CST not connected")

    result_tools._solver_band = _boom  # type: ignore[assignment]
    result_tools._sess = lambda: FakeSession(51.95)  # type: ignore[assignment]
    out = _handler()(operating_frequency=2.4)
    degraded = "WARNING" in str(out.get("verdict", ""))
    print(f"[{'PASS' if degraded else 'FAIL'}] explicit frequency still works when the band read fails")
    print(f"        verdict: {str(out.get('verdict'))[:130]}")
    results.append(degraded)

    # and with no explicit frequency either, a broken band read gives UNKNOWN
    result_tools._solver_band = _boom  # type: ignore[assignment]
    out = _handler()(operating_frequency=None)
    graceful = "UNKNOWN" in str(out.get("verdict", ""))
    print(f"[{'PASS' if graceful else 'FAIL'}] broken band read with no argument degrades to UNKNOWN")
    print(f"        verdict: {str(out.get('verdict'))[:130]}")
    results.append(graceful)

    result_tools._solver_band = _REAL_SOLVER_BAND  # type: ignore[assignment]

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
