"""Regression tests for the project-overwrite path (`cst_save_project_tool`).

Bug pinned: `save_project(overwrite=True)` deleted only the `.cst` file and then
called CST's `save(path)`. That leaves the companion directory - `Model/`, `Result/` -
in place, and CST answers with

    Failed to save project. The project directory <dir> already exists and is
    non-empty. It would be overwritten.

which interactively is the confirmation about the previous results, so an unattended
iterative run stalled on a click. It also left an orphaned directory behind: the
`.cst` was gone, the results were not.

Verified live on CST 2026.2 (docs/dev/verification.md):
  * `save(path)` alone refuses an existing target;
  * deleting only the `.cst` does not help - the directory check still fires;
  * `save(path, allow_overwrite=True)` succeeds **after** the project occupying that
    path is closed; while it is open, `Model/` and `Result/` are locked and CST fails
    with a bare "Failed to save project";
  * CST then replaces the `.cst` and the companion directory itself, so this server
    never has to delete project files.

The suite is offline: the DE and the project are stubs recording what they were asked
to do.

Run: python tests/test_save_overwrite.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cst_mcp.session import CSTError, CSTSession  # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool) -> None:
    RESULTS.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")


class FakeProject:
    """Records save() calls instead of talking to CST."""

    def __init__(self, path: Path) -> None:
        self._path = str(path)
        self.calls: list[dict] = []

    def filename(self) -> str:
        return self._path

    def folder(self) -> str:
        return str(Path(self._path).with_suffix(""))

    def save(self, path: str = "", include_results: bool = True, allow_overwrite: bool = False) -> None:
        self.calls.append(
            {"path": str(path), "include_results": include_results, "allow_overwrite": bool(allow_overwrite)}
        )


class FakeHandle:
    def __init__(self, de: "FakeDE", path: str) -> None:
        self.de, self.path = de, path

    def close(self) -> None:
        if self.de.fail_close:
            raise RuntimeError("close refused")
        self.de.open.remove(self.path)
        self.de.closed.append(self.path)


class FakeDE:
    def __init__(self, open_paths=(), fail_close: bool = False) -> None:
        self.open = list(open_paths)
        self.closed: list[str] = []
        self.fail_close = fail_close

    def list_open_projects(self):
        return list(self.open)

    def get_open_project(self, path):
        return FakeHandle(self, path)


def make_session(active: Path, open_paths=(), fail_close: bool = False):
    sess = CSTSession()
    de = FakeDE(open_paths, fail_close)
    sess._de = de
    sess._project = FakeProject(active)
    return sess, de


def make_bundle(path: Path, entries=("Model", "Result")) -> Path:
    """Create a minimal project bundle: the .cst file plus its companion directory."""
    path.write_text("cst", encoding="utf-8")
    bundle = path.with_suffix("")
    for name in entries:
        (bundle / name).mkdir(parents=True, exist_ok=True)
        (bundle / name / "x").write_text("x", encoding="utf-8")
    return bundle


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        active = make_bundle(tmpdir / "active.cst")

        # 1. Without overwrite, an existing project is refused - and nothing is saved.
        target = make_bundle(tmpdir / "A.cst")
        sess, de = make_session(active)
        try:
            sess.save_project(path=str(target), overwrite=False)
            check("refuses an existing project without overwrite", False)
        except CSTError as exc:
            check("refuses an existing project without overwrite", "refusing to overwrite" in str(exc))
        check("refused call never reaches CST save()", sess._project.calls == [])

        # 2. A companion directory alone (no .cst) still counts as existing.
        lonely = tmpdir / "B"
        lonely.mkdir()
        (lonely / "Result").mkdir()
        (lonely / "Result" / "y").write_text("y", encoding="utf-8")
        sess, de = make_session(active)
        try:
            sess.save_project(path=str(tmpdir / "B.cst"), overwrite=False)
            check("a non-empty companion directory alone counts as existing", False)
        except CSTError:
            check("a non-empty companion directory alone counts as existing", True)

        # 3. overwrite=True goes through CST's own allow_overwrite flag.
        target = make_bundle(tmpdir / "C.cst")
        sess, de = make_session(active)
        out = sess.save_project(path=str(target), overwrite=True)
        call = sess._project.calls[-1]
        check("overwrite passes allow_overwrite=True", call["allow_overwrite"] is True)
        check("overwrite reports overwritten=True", out.get("overwritten") is True)

        # 4. The project occupying that path is closed first - it holds the locks.
        target = make_bundle(tmpdir / "D.cst")
        sess, de = make_session(active, open_paths=[str(target), str(active)])
        sess.save_project(path=str(target), overwrite=True)
        check("closes the project occupying the target path", de.closed == [str(target)])
        check("does not close an unrelated open project", str(active) not in de.closed)

        # 5. This server never deletes project files itself.
        target = make_bundle(tmpdir / "E.cst")
        sess, de = make_session(active)
        sess.save_project(path=str(target), overwrite=True)
        check("leaves the .cst on disk (CST replaces it, not us)", target.exists())
        check("leaves the companion directory on disk", target.with_suffix("").is_dir())

        # 6. Saving the active project onto its own path stays an in-place save.
        osess, ode = make_session(active, open_paths=[str(active)])
        out = osess.save_project(path=str(active), overwrite=True)
        check("in-place save when the target is the active project", ode.closed == [])
        check(
            "in-place save does not ask CST to overwrite",
            osess._project.calls[-1]["allow_overwrite"] is False,
        )
        check("in-place save reports overwritten=False", out.get("overwritten") is False)

        # 7. A project that cannot be closed reports why, instead of a bare failure.
        target = make_bundle(tmpdir / "F.cst")
        sess, de = make_session(active, open_paths=[str(target)], fail_close=True)
        try:
            sess.save_project(path=str(target), overwrite=True)
            check("a project that cannot be closed raises a located error", False)
        except CSTError as exc:
            check("a project that cannot be closed raises a located error", "could not" in str(exc))
        check("nothing was saved when the close failed", sess._project.calls == [])

    failed = [label for label, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("failed:")
        for label in failed:
            print(f"  - {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
