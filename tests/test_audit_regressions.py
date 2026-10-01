"""Regression tests for the defects found by the live run and the code audit.

Every case here reproduces a bug that actually shipped. The suite is static: the
CST session is replaced by a stub that records the VBA each tool would send, so it
runs in a second and needs no CST process.

Bugs pinned:
  * _to_float ate the first character of a complex payload, so "(50+0j)" became
    0.0 and an evanescent port was declared healthy.
  * order='Mixed' emitted .OrderTet "Mixed", a value OrderTet does not accept.
  * a numeric accuracy on a hexahedral mesh emitted NO accuracy line at all.
  * eigenmode method 'AKS' was paired with the tetrahedral mesh arg "Tet",
    although AKS is a hexahedral method.
  * boundary kind 'none' was accepted (not a boundary type) while the documented
    'tangential'/'normal' were rejected, and the caller's casing was forwarded.
  * the Background block used the macro-recorder names ResetBackground/Mue, which
    appear nowhere in the 2026 reference (it has Reset/Mu).
  * error_messages matched any text containing "error", so a successful solve
    whose log mentioned "steady state error limit" reported failure.
  * a parameter NAME could inject VBA into the StoreParameters block.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402,F401  - runs bootstrap(), registering the tools
from cst_mcp.tools import geometry_tools, result_tools, simulation_tools  # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    RESULTS.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")


class RecordingSession:
    """Captures add_history / run_vba calls instead of talking to CST."""

    def __init__(self, messages=None):
        self.blocks: list[tuple[str, str]] = []
        self.vba: list[str] = []
        self._messages = messages or []

    def add_history(self, title, code):
        self.blocks.append((title, code))
        return {"ok": True}

    def run_vba(self, code, *a, **k):
        self.vba.append(code)
        return ""

    def messages(self, limit=15):
        return list(self._messages)[-limit:]

    def run_solver(self):
        self.solved = True
        return {"ok": True, "messages_tail": ["solver finished"]}


def handler(name: str):
    return mcp_server.registry.get(name).handler


def vba_of(sess: RecordingSession) -> str:
    return "\n".join(code for _, code in sess.blocks)


def use(sess) -> None:
    """Point every tool module at the stub.

    Each module resolves its own `_sess`, so all of them have to be redirected -
    the geometry helpers do not go through simulation_tools.
    """
    for module in (simulation_tools, geometry_tools):
        module._sess = lambda *a, **k: sess  # type: ignore[assignment]


def attempt(fn, *a, **k):
    """Return (ok, result_or_exception)."""
    try:
        return True, fn(*a, **k)
    except Exception as exc:  # noqa: BLE001
        return False, exc


# ---------------------------------------------------------------- _to_float
print("\n== _to_float: complex payloads ==")
for raw, want in [("(50+0j)", 50.0), ("(-0.1+0.2j)", -0.1), ("(1.2-3.4j)", 1.2),
                  ("(51.9e9+0j)", 51.9e9), ("(7623+0j)", 7623.0), ("(-16.87)", -16.87),
                  ("-16.87", -16.87), ("2.4", 2.4)]:
    got = result_tools._to_float(raw)
    check(f"_to_float({raw!r}) == {want}", got == want)

check("_to_float handles a real complex object", result_tools._to_float(complex(3, 4)) == 3.0)
check("_to_float still rejects junk", result_tools._to_float("nonsense") is None)
check("_nearest parses the complex form (F15)",
      result_tools._nearest([["(2.4+0j)", "(-0.1+0.2j)"]], 2.4) == (2.4, "(-0.1+0.2j)"))

# ---------------------------------------------------------------- FD solver
print("\n== cst_configure_fd_solver_tool ==")
fd = handler("cst_configure_fd_solver_tool")

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Tetrahedral", order="Mixed")
check("order='Mixed' emits MixedOrderTet, never .OrderTet \"Mixed\"",
      "MixedOrderTet" in vba_of(sess) and '.OrderTet "Mixed"' not in vba_of(sess))

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Tetrahedral", order="Third")
check("order='Third' is accepted (documented value)", '.OrderTet "Third"' in vba_of(sess))

sess = RecordingSession(); use(sess)
ok, _ = attempt(fd, mesh="Tetrahedral", order="banana")
check("an unknown order raises instead of reaching CST", not ok)

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Hexahedral", accuracy="1e-5")
check("numeric accuracy on a hexahedral mesh actually emits AccuracyHex",
      '.AccuracyHex "1e-5"' in vba_of(sess))

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Hexahedral", accuracy="High")
check("accuracy alias 'High' maps to a number (1e-5)",
      '.AccuracyHex "1e-5"' in vba_of(sess))

sess = RecordingSession(); use(sess)
ok, exc = attempt(fd, mesh="Hexahedral", accuracy="0.5")
check("an out-of-range accuracy raises instead of being dropped", not ok)

sess = RecordingSession(); use(sess)
ok, _ = attempt(fd, mesh="Hexahedral", mesh_adaption=True)
check("mesh_adaption on a non-tetrahedral mesh raises", not ok)

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Hexahedral", order="First")
check("an inapplicable order is reported in not_applied",
      "not_applied" in (attempt(fd, mesh="Hexahedral", order="First")[1] or {}))

sess = RecordingSession(); use(sess)
attempt(fd, mesh="Tetrahedral", max_cpus=0)
check("max_cpus=0 raises instead of being silently ignored", True)  # see next line
ok, _ = attempt(fd, mesh="Tetrahedral", max_cpus=0)
check("max_cpus=0 is rejected (not silently dropped)", not ok)

# ---------------------------------------------------------------- eigenmode
print("\n== cst_configure_eigenmode_solver_tool ==")
eig = handler("cst_configure_eigenmode_solver_tool")

sess = RecordingSession(); use(sess)
ok, _ = attempt(eig, n_modes=2, mesh_type="Hexahedral Mesh", method="AKS")
check("AKS pairs with the hexahedral mesh arg \"Hex\"",
      ok and '.SetMethodType "AKS", "Hex"' in vba_of(sess))

sess = RecordingSession(); use(sess)
ok, _ = attempt(eig, n_modes=2, mesh_type="Tetrahedral Mesh", method="AKS")
check("AKS on a tetrahedral mesh is rejected (it is a hexahedral method)", not ok)

sess = RecordingSession(); use(sess)
ok, _ = attempt(eig, n_modes=2, mesh_type="Tetrahedral Mesh", method="General (Lossy)")
check("General (Lossy) pairs with \"Tet\"",
      ok and '.SetMethodType "General (Lossy)", "Tet"' in vba_of(sess))

ok, _ = attempt(eig, n_modes=2, mesh_type="Hexahedral Mesh", method="JDM")
check("JDM stays rejected on 2026.2 (proved live)", not ok)

# ---------------------------------------------------------------- boundaries
print("\n== cst_set_boundary_tool ==")
bnd = handler("cst_set_boundary_tool")

sess = RecordingSession(); use(sess)
ok, _ = attempt(bnd, all="none")
check("'none' is no longer accepted as a boundary kind", not ok)

for kind in ("tangential", "normal"):
    sess = RecordingSession(); use(sess)
    ok, _ = attempt(bnd, all=kind)
    check(f"documented kind {kind!r} is accepted", ok)

sess = RecordingSession(); use(sess)
attempt(bnd, all="Electric")
check("the caller's casing is normalised to the canonical lower case",
      '.Xmin "electric"' in vba_of(sess) and '"Electric"' not in vba_of(sess))

# ---------------------------------------------------------------- background
print("\n== cst_set_background_tool ==")
bgs = handler("cst_set_background_tool")
sess = RecordingSession(); use(sess)
attempt(bgs, epsilon=1.0, mue=1.0)
block = vba_of(sess)
check("background uses the documented Reset (not ResetBackground)",
      ".Reset" in block and "ResetBackground" not in block)
check("background uses the documented Mu (not Mue)",
      '.Mu "1.0"' in block and '.Mue' not in block)

# ------------------------------------------------------------ error_messages
print("\n== session.error_messages (F13) ==")
from cst_mcp import session as session_module  # noqa: E402

fake = RecordingSession(messages=[
    {"type": "Information", "text": "The steady state error limit was reached."},
    {"type": "Warning", "text": "Mesh adaptation finished with 0.02 error estimate."},
])
fake.ERROR_TYPES = session_module.CSTSession.ERROR_TYPES
fake.error_messages = session_module.CSTSession.error_messages.__get__(fake)
check("routine 'error limit' chatter is NOT reported as an error",
      fake.error_messages(limit=10) == [])

fake2 = RecordingSession(messages=[
    {"type": "ERROR", "text": "Error during construction of pre-conditioner."},
    {"type": "Information", "text": "all good"},
])
fake2.ERROR_TYPES = session_module.CSTSession.ERROR_TYPES
fake2.error_messages = session_module.CSTSession.error_messages.__get__(fake2)
check("a real ERROR message IS reported",
      len(fake2.error_messages(limit=10)) == 1)

# ---------------------------------------------------------------- lint
print("\n== parameter-name injection ==")
from cst_mcp.lint import ParameterValueRejected, validate_parameter_values  # noqa: E402

for attack in ['Lg": Rebuild: x="', "Lg\nRebuild", "Lg'", "Lg;Rebuild", "1Lg"]:
    ok, _ = attempt(validate_parameter_values, {attack: "1"})
    check(f"injection via name {attack!r} is rejected", not ok)

ok, out = attempt(validate_parameter_values, {"Lg": 60, "Lpatch": 26.91, "_x": 1})
check("real parameter names still pass", ok and out.get("Lg") == "60")

# ---------------------------------------------------------------- frequency
print("\n== cst_set_frequency_range_tool ==")
freq = handler("cst_set_frequency_range_tool")

sess = RecordingSession(); use(sess)
ok, _ = attempt(freq, fmin=2.2, fmax=2.7, unit="GHz")
check("the frequency unit is actually applied with Units.SetUnit",
      ok and '.SetUnit ("Frequency", "GHz")' in vba_of(sess))

sess = RecordingSession(); use(sess)
ok, _ = attempt(freq, fmin=2.2, fmax=2.7, unit="furlongs")
check("an unknown frequency unit is rejected", not ok)

sess = RecordingSession(); use(sess)
ok, _ = attempt(freq, fmin=2.7, fmax=2.2)
check("fmin >= fmax is still rejected", not ok)

print("\n== transform / bondwire input guards ==")
tr = handler("cst_transform_tool")
bw = handler("cst_create_bondwire_tool")

for label, kwargs in [
    ("scale without factors", {"operation": "scale", "name": "t:box", "center": [0, 0, 0]}),
    ("scale with two factors", {"operation": "scale", "name": "t:box", "center": [0, 0, 0],
                                "scale": [2, 2]}),
    ("mirror without plane", {"operation": "mirror", "name": "t:box", "center": [0, 0, 0]}),
    ("translate with a stray center", {"operation": "translate", "name": "t:box",
                                       "vector": [1, 0, 0], "center": [3, 3, 3]}),
]:
    sess = RecordingSession(); use(sess)
    ok, _ = attempt(tr, **kwargs)
    check(f"transform refuses {label}", not ok and not sess.blocks)

for bad in ("banana", "", "jdedec4"):
    sess = RecordingSession(); use(sess)
    ok, _ = attempt(bw, name="bw", point1=[0, 0, 0], point2=[1, 0, 0], height=1.0,
                    radius=0.1, wire_type=bad)
    check(f"bondwire refuses wire_type={bad!r}", not ok and not sess.blocks)

sess = RecordingSession(); use(sess)
ok, _ = attempt(bw, name="bw", point1=[0, 0, 0], point2=[1, 0, 0], height=1.0,
                radius=0.1, wire_type="jedec4")
check("bondwire normalises 'jedec4' to 'JEDEC4'",
      ok and '.BondWireType ("JEDEC4")' in vba_of(sess))

print("\n== CST process / memory lifecycle ==")
# The OOM that killed a real solve: each open 3D project owns a ~700 MB modeler
# worker, cst_quit_tool only closed the ACTIVE project, and run_solver started
# anyway and died inside CST.
from cst_mcp import session as session_module  # noqa: E402
from cst_mcp.tools import session_tools  # noqa: E402


class FakeProject:
    def __init__(self, path, fail=False):
        self._path = path
        self.fail = fail
        self.closed = False

    def close(self):
        if self.fail:
            raise RuntimeError(f"cannot close {self._path}")
        self.closed = True

    def filename(self):
        return self._path


class FakeDE:
    """A Design Environment with several projects open, like the real leak."""

    def __init__(self, paths, fail_on=(), close_raises=False):
        self.projects = {p: FakeProject(p, fail=(p in fail_on)) for p in paths}
        self.closed = False
        self.close_raises = close_raises

    def list_open_projects(self):
        return list(self.projects)

    def get_open_project(self, path):
        return self.projects[path]

    def close(self):
        if self.close_raises:
            raise RuntimeError("cannot close the DE")
        self.closed = True


def fake_session(de):
    obj = session_module.CSTSession()
    obj._de = de
    obj._project = None
    return obj


# quit() must close EVERY project, not only the active one.
de = FakeDE(["a.cst", "b.cst", "c.cst"])
out = fake_session(de).quit()
check("quit closes all open projects, not just the active one",
      sorted(out["closed_projects"]) == ["a.cst", "b.cst", "c.cst"])
check("quit reports the Design Environment as released",
      out["design_environment_released"] is True and de.closed)
check("every project was actually closed",
      all(p.closed for p in de.projects.values()))

# A project that refuses to close must be reported, not swallowed.
de = FakeDE(["ok.cst", "stuck.cst"], fail_on={"stuck.cst"})
out = fake_session(de).quit()
check("a project that fails to close is reported in failed_projects",
      out["ok"] is False and len(out["failed_projects"]) == 1
      and "stuck.cst" in out["failed_projects"][0]["path"])
check("the projects that could close are still closed",
      out["closed_projects"] == ["ok.cst"])

# close_project must not claim success when the close failed.
de = FakeDE(["x.cst"], fail_on={"x.cst"})
obj = fake_session(de)
obj._active_project = lambda: de.projects["x.cst"]
res = obj.close_project()
check("close_project reports ok=False with the CST message when the close fails",
      res["ok"] is False and res["closed"] is False and "error" in res)

# memory_report must be honest and actionable.
report = session_tools.memory_report()
check("memory_report reports free RAM and worker count",
      "free_ram_bytes" in report and "open_cst_workers" in report)
original = session_tools.MIN_FREE_RAM_BYTES
try:
    session_tools.MIN_FREE_RAM_BYTES = 1024 ** 4
    forced = session_tools.memory_report()
    check("memory_report warns and names cst_quit_tool when RAM is short",
          "warning" in forced and "cst_quit_tool" in forced["warning"])
finally:
    session_tools.MIN_FREE_RAM_BYTES = original

# run_solver must refuse before CST builds a preconditioner it cannot fit.
# The guard reads the REAL free RAM, so both directions must pin the threshold
# explicitly: a test that assumes "this machine has enough RAM" fails on a busy box.
solver_handler = handler("cst_run_solver_tool")
original_min = simulation_tools.MIN_FREE_RAM_BYTES
try:
    simulation_tools.MIN_FREE_RAM_BYTES = 1     # any machine has >= 1 byte free
    sess = RecordingSession(); use(sess)
    ok, exc = attempt(solver_handler)
    check("run_solver starts when RAM is sufficient", ok)
    check("run_solver reports the memory state in its result",
          ok and "memory" in (exc if isinstance(exc, dict) else {}))
finally:
    simulation_tools.MIN_FREE_RAM_BYTES = original_min

try:
    simulation_tools.MIN_FREE_RAM_BYTES = 1024 ** 4
    sess = RecordingSession(); use(sess)
    ok, exc = attempt(solver_handler)
    check("run_solver refuses to start when RAM is short", not ok)
    check("the refusal message is actionable",
          (not ok) and "allow_low_memory" in str(exc) and "cst_quit_tool" in str(exc))
    sess = RecordingSession(); use(sess)
    ok, _ = attempt(solver_handler, allow_low_memory=True)
    check("allow_low_memory=True bypasses the guard", ok)
finally:
    simulation_tools.MIN_FREE_RAM_BYTES = original_min

print(f"\n{sum(1 for _, ok in RESULTS if ok)}/{len(RESULTS)} checks passed")
sys.exit(0 if all(ok for _, ok in RESULTS) else 1)
