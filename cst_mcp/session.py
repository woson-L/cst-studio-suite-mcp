"""CST session layer: exactly one Design Environment, robust across MCP calls.

Key behaviours this module guarantees
------------------------------------
* One Design Environment is created on demand and reused.
* A tool call never depends on session state that a previous MCP call happened to
  leave behind: the active project is re-discovered from CST when needed.
* A new project is saved into CST_MCP_WORKSPACE immediately, so it cannot be lost
  in a temporary folder between calls.
* Per-tool-call timeouts are not used; every call is bounded by CST itself.
"""
from __future__ import annotations

import contextlib
import importlib
import json
import time
from pathlib import Path
from typing import Any

from . import config

_CST_PATHS_READY = False


class CSTError(RuntimeError):
    """Raised when CST cannot be reached or a command fails."""


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if hasattr(value, "tolist"):
        with contextlib.suppress(Exception):
            return _jsonable(value.tolist())
    return repr(value)


def dumps(data: Any) -> str:
    return json.dumps(_jsonable(data), ensure_ascii=False, indent=2)


def _load(name: str) -> Any:
    global _CST_PATHS_READY
    if not _CST_PATHS_READY:
        config.ensure_cst_paths()
        _CST_PATHS_READY = True
    try:
        return importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        raise CSTError(
            f"cannot import {name!r}. Check CST_INSTALL_ROOT in .env "
            f"(currently {config.cst_root()}). Original error: {exc}"
        ) from exc


def cst_interface() -> Any:
    return _load("cst.interface")


def cst_results() -> Any:
    return _load("cst.results")


class CSTSession:
    """Owns the Design Environment and the active project."""

    def __init__(self) -> None:
        self._de: Any = None
        self._project: Any = None

    # ------------------------------------------------------------------ DE
    @property
    def de(self) -> Any:
        if self._de is None:
            ci = cst_interface()
            try:
                self._de = ci.DesignEnvironment.connect_to_any()
            except Exception:
                self._de = ci.DesignEnvironment.connect_to_any_or_new()
        return self._de

    def connect(self, *, launch_if_needed: bool = True) -> dict[str, Any]:
        ci = cst_interface()
        running = list(ci.running_design_environments())
        if launch_if_needed:
            self._de = ci.DesignEnvironment.connect_to_any_or_new()
        else:
            self._de = ci.DesignEnvironment.connect_to_any()
        return self.info()

    def detect(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "cst_install_root": str(config.cst_root()),
            "cst_exe": str(config.cst_exe()),
            "cst_exe_exists": config.cst_exe().is_file(),
            "workspace": str(config.workspace()),
            "evidence_dir": str(config.evidence_dir()),
            "python_executable": __import__("sys").executable,
        }
        try:
            info["cst_interface_importable"] = True
            info["running_design_environments"] = list(cst_interface().running_design_environments())
        except Exception as exc:  # noqa: BLE001
            info["cst_interface_importable"] = False
            info["cst_interface_error"] = f"{type(exc).__name__}: {exc}"
        try:
            results = cst_results()
            info["cst_results_importable"] = True
            version = getattr(results, "get_version_info", None)
            if callable(version):
                info["cst_results_version"] = _jsonable(version())
        except Exception as exc:  # noqa: BLE001
            info["cst_results_importable"] = False
            info["cst_results_error"] = f"{type(exc).__name__}: {exc}"
        info["ready"] = bool(
            info.get("cst_interface_importable") and info.get("cst_results_importable")
        )
        return info

    def info(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "connected": self._de is not None,
            "design_environment_pid": None,
            "has_active_project": False,
            "open_projects": [],
            "active_project": None,
            "messages_tail": [],
        }
        if self._de is None:
            return out
        with contextlib.suppress(Exception):
            out["design_environment_pid"] = self._de.pid()
        with contextlib.suppress(Exception):
            out["open_projects"] = [str(p) for p in self._de.list_open_projects()]
        prj = self._active_project()
        if prj is not None:
            out["has_active_project"] = True
            with contextlib.suppress(Exception):
                out["active_project"] = {
                    "filename": str(prj.filename()),
                    "folder": str(prj.folder()),
                }
            msgs = self.messages(limit=15, project=prj)
            if msgs:
                out["messages_tail"] = msgs
        return out

    # ------------------------------------------------------------- project
    def _active_project(self) -> Any:
        if self._project is not None:
            with contextlib.suppress(Exception):
                if self._project.filename():
                    return self._project
            self._project = None
        if self._de is None:
            return None
        with contextlib.suppress(Exception):
            self._project = self._de.active_project()
        return self._project

    def project(self) -> Any:
        prj = self._active_project()
        if prj is None:
            raise CSTError(
                "no active CST project. Create one with cst_new_project_tool, "
                "open one with cst_open_project_tool, or call cst_connect_tool."
            )
        return prj

    def model3d(self) -> Any:
        return self.project().model3d

    def new_project(self, project_type: str = "mws", path: str | None = None) -> dict[str, Any]:
        de = self.de
        factory = {
            "mws": "new_mws", "microwave": "new_mws", "ems": "new_ems", "em": "new_ems",
            "ps": "new_ps", "particle": "new_ps", "mps": "new_mps", "multiphysics": "new_mps",
            "cs": "new_cs", "cable": "new_cs", "pcbs": "new_pcbs", "pcb": "new_pcbs",
            "ds": "new_ds", "designstudio": "new_ds", "fd3d": "new_fd3d",
        }.get(project_type.strip().lower())
        if factory is None:
            raise CSTError(f"unknown project_type {project_type!r}")
        self._project = getattr(de, factory)()
        target = self._default_project_path() if not path else config.resolve_path(path)
        saved = self.save_project(str(target))
        out = self.info()
        out["saved_to"] = saved.get("path")
        return out

    def _default_project_path(self) -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = config.workspace() / f"Project_{stamp}.cst"
        index = 1
        while base.exists():
            base = config.workspace() / f"Project_{stamp}_{index}.cst"
            index += 1
        return base

    def save_project(self, path: str | None = None, overwrite: bool = False) -> dict[str, Any]:
        prj = self.project()
        if path and str(path).strip():
            target = config.resolve_path(path)
            # If CST already has this file open as the active project, a plain save()
            # is both correct and safest: deleting the file out from under an open
            # project would leave CST inconsistent.
            try:
                current = Path(prj.filename()).resolve(strict=False)
            except Exception:  # noqa: BLE001 - filename() is best-effort
                current = None
            if current is not None and current == target.resolve(strict=False):
                prj.save()
                return {"ok": True, "path": str(target), "overwritten": False,
                        "note": "already the active project file; saved in place"}

            target.parent.mkdir(parents=True, exist_ok=True)
            # CST refuses a save onto an existing project in two different ways:
            #   "The given path already exists <file>"
            #   "The project directory <dir> already exists and is non-empty.
            #    It would be overwritten."
            # The second one is what stops an unattended run: interactively it is the
            # confirmation asking about the previous results, and through the
            # automation interface it comes back as a hard failure.
            #
            # A CST project is the .cst file *plus* a companion directory of the same
            # stem holding Model/ and Result/. Deleting only the .cst - what this used
            # to do - leaves that directory and its results behind, so the save still
            # fails and the run is left with an orphaned project directory.
            #
            # Verified on CST 2026.2 (docs/dev/verification.md):
            #   * save(path, allow_overwrite=True) succeeds, and CST replaces the .cst
            #     and the companion directory itself;
            #   * it only succeeds once the project occupying that path is closed -
            #     Model/ and Result/ stay locked while it is open and the call then
            #     fails with a bare "Failed to save project".
            existed = target.exists() or self._bundle_is_non_empty(target)
            if existed and not overwrite:
                raise CSTError(
                    f"refusing to overwrite the existing project {target}. "
                    f"Pass overwrite=True to replace it, or choose another path."
                )
            if existed:
                self._close_open_projects_at(target)
            prj.save(str(target), allow_overwrite=overwrite)
            return {"ok": True, "path": str(target), "overwritten": existed}
        prj.save()
        with contextlib.suppress(Exception):
            return {"ok": True, "path": str(prj.filename())}
        return {"ok": True, "path": None}

    # ------------------------------------------------- overwrite support
    @staticmethod
    def _project_bundle(path: Path) -> Path:
        """The companion directory of a project: ``<name>.cst`` -> ``<name>``."""
        return path.with_suffix("")

    @staticmethod
    def _bundle_is_non_empty(path: Path) -> bool:
        bundle = CSTSession._project_bundle(path)
        try:
            return bundle.is_dir() and any(bundle.iterdir())
        except OSError:
            # An unreadable directory is one an open project holds; treat it as occupied.
            return True

    def _close_open_projects_at(self, target: Path) -> list[str]:
        """Close every open project occupying *target* so its files are released.

        A locked Model/ or Result/ makes ``save(..., allow_overwrite=True)`` fail with
        a bare "Failed to save project", so the old project has to go first. Closing is
        implied by ``overwrite=True``: the caller asked for that path to be replaced.
        """
        de = self._de
        if de is None:
            return []
        key = target.resolve(strict=False)
        bundle = self._project_bundle(key)
        closed: list[str] = []
        try:
            open_paths = list(de.list_open_projects())
        except Exception:  # noqa: BLE001 - no listing means nothing we can close
            return []
        for path in open_paths:
            try:
                other = Path(path).resolve(strict=False)
            except Exception:  # noqa: BLE001 - a stale handle is not our problem
                continue
            if other != key and self._project_bundle(other) != bundle:
                continue
            try:
                de.get_open_project(path).close()
                closed.append(str(path))
            except Exception as exc:  # noqa: BLE001
                raise CSTError(
                    f"cannot overwrite {target}: the project {path} is open and could not "
                    f"be closed ({type(exc).__name__}: {exc}). Its Model/ and Result/ "
                    f"files stay locked while it is open."
                ) from exc
        return closed

    def open_project(self, path: str) -> dict[str, Any]:
        target = config.resolve_path(path)
        if not target.is_file():
            raise CSTError(f"project not found: {target}")
        self._project = self.de.open_project(str(target))
        return self.info()

    def close_project(self) -> dict[str, Any]:
        prj = self._active_project()
        closed = False
        error = None
        if prj is not None:
            try:
                prj.close()
                closed = True
            except Exception as exc:  # noqa: BLE001
                # Previously suppressed: a failed close still returned ok=True with
                # closed=False, so the failure was invisible to the caller.
                error = f"{type(exc).__name__}: {exc}"
        self._project = None
        result: dict[str, Any] = {"ok": error is None, "closed": closed}
        if error is not None:
            result["error"] = error
        return result

    def close_all_projects(self) -> dict[str, Any]:
        """Close EVERY open project, not just the active one.

        Each open 3D project owns its own `modeler_AMD64.exe` worker of roughly
        700 MB. Measured on this machine: five projects left open held ~3.5 GB, and
        the next frequency-domain solve died with "Error during construction of
        pre-conditioner. Not enough memory." Closing the projects reaped all five
        workers immediately (verified against the live process list).
        """
        de = self.de
        try:
            paths = list(de.list_open_projects())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "closed": [], "failed": [],
                    "error": f"{type(exc).__name__}: {exc}"}
        closed: list[str] = []
        failed: list[dict[str, str]] = []
        for path in paths:
            try:
                project = de.get_open_project(path)
                project.close()
                closed.append(str(path))
            except Exception as exc:  # noqa: BLE001
                failed.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        self._project = None
        return {"ok": not failed, "closed": closed, "failed": failed}

    def quit(self) -> dict[str, Any]:
        """Close every project and release the Design Environment process.

        `DesignEnvironment.close()` terminates the CST process itself (verified
        live: the DE pid disappears and every modeler worker with it).
        """
        projects = self.close_all_projects()
        released = False
        error = None
        de = self._de
        if de is not None:
            try:
                de.close()
                released = True
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
        self._de = None
        self._project = None
        result: dict[str, Any] = {
            "ok": error is None and bool(projects.get("ok")),
            "closed_projects": projects.get("closed", []),
            "failed_projects": projects.get("failed", []),
            "design_environment_released": released,
        }
        if error is not None:
            result["error"] = error
        return result

    def messages(self, limit: int = 20, project: Any = None) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        prj = project
        if prj is None:
            prj = self._active_project()
        if prj is None:
            return out
        with contextlib.suppress(Exception):
            raw = prj.get_messages()
            if isinstance(raw, list):
                for entry in raw[-limit:]:
                    if isinstance(entry, dict):
                        out.append({
                            "type": str(entry.get("type", "")),
                            "text": str(entry.get("text", "")),
                        })
                    else:
                        out.append({"type": "", "text": str(entry)})
        return out

    #: Message types CST uses for a genuine failure. Matching on the type is the
    #: only reliable test: the previous version also matched any message whose TEXT
    #: contained the substring "error", which caught routine lines such as
    #: "The steady state error limit was reached." and "Mesh adaptation finished
    #: with 0.02 error estimate" - so cst_run_solver_tool reported failure on
    #: perfectly successful solves.
    ERROR_TYPES = ("ERROR", "ERRORS", "FATAL", "SEVERE")

    def error_messages(self, limit: int = 10) -> list[str]:
        out: list[str] = []
        for message in self.messages(limit=limit):
            kind = message["type"].strip().upper()
            if kind in self.ERROR_TYPES:
                out.append(f"{message['type']}: {message['text']}".strip(": "))
        return out

    # ----------------------------------------------------------------- VBA
    def run_vba(self, code: str) -> dict[str, Any]:
        """Execute a VBA block with a Sub Main wrapper."""
        if not code.strip():
            raise CSTError("vba code must not be empty")
        body = code if "sub main" in code.lower() else f"Sub Main\n{code}\nEnd Sub"
        try:
            self.model3d()._execute_vba_code(body)
        except Exception as exc:  # noqa: BLE001
            raise CSTError(f"{type(exc).__name__}: {exc}") from exc
        return {"ok": True}

    def add_history(self, title: str, code: str) -> dict[str, Any]:
        """Append one named block to the model history tree."""
        from .lint import lint_history_block

        if not title.strip():
            raise CSTError("title must not be empty")
        if not code.strip():
            raise CSTError("vba_code must not be empty")
        lint_history_block(title.strip(), code)
        try:
            self.model3d().add_to_history(title.strip(), code)
        except Exception as exc:  # noqa: BLE001
            tail = self.error_messages(limit=5)
            detail = f"{type(exc).__name__}: {exc}"
            if tail:
                detail += "\nCST messages:\n  " + "\n  ".join(tail)
            raise CSTError(detail) from exc
        return {"ok": True, "title": title.strip()}

    # --------------------------------------------------------------- solve
    def run_solver(self) -> dict[str, Any]:
        prj = self.project()
        try:
            prj.model3d.run_solver()
        except Exception as exc:  # noqa: BLE001
            tail = self.error_messages(limit=10)
            detail = f"{type(exc).__name__}: {exc}"
            if tail:
                detail += "\nCST messages:\n  " + "\n  ".join(tail)
            return {"ok": False, "error": detail, "messages_tail": tail}
        tail = self.error_messages(limit=10)
        if tail:
            return {"ok": False, "error": "CST reported errors:\n  " + "\n  ".join(tail), "messages_tail": tail}
        return {"ok": True, "messages_tail": self.messages(limit=6)}

    # ------------------------------------------------------------- results
    def _results_module(self, cst_file: str | None, module: str) -> Any:
        path = cst_file or str(self.project().filename())
        if not path:
            raise CSTError("the project has no filename yet; save it first")
        pf = cst_results().ProjectFile(path, allow_interactive=True)
        key = (module or "3d").lower()
        if key in {"3d", "model3d", "mws"}:
            return pf.get_3d()
        if key in {"schematic", "ds"}:
            return pf.get_schematic()
        raise CSTError("module must be '3d' or 'schematic'")

    def list_results(self, cst_file: str | None = None, module: str = "3d") -> dict[str, Any]:
        items = list(self._results_module(cst_file, module).get_tree_items())
        return {"ok": True, "count": len(items), "items": items}

    def read_result(self, tree_path: str, cst_file: str | None = None,
                    module: str = "3d", max_points: int = 4000) -> dict[str, Any]:
        if not tree_path.strip():
            raise CSTError("tree_path must not be empty")
        rm = self._results_module(cst_file, module)
        item = rm.get_result_item(tree_path.strip())
        data = item.get_data()
        rows = list(data[:max_points]) if hasattr(data, "__getitem__") else list(data)
        return {
            "ok": True,
            "tree_path": tree_path.strip(),
            "title": getattr(item, "title", None) if not callable(getattr(item, "title", None)) else item.title(),
            "length": len(data) if hasattr(data, "__len__") else None,
            "returned_points": len(rows),
            "data": _jsonable(rows),
        }

    # --------------------------------------------------------------- misc
    def parameter(self, name: str) -> str | None:
        """Read one design parameter through the CST application object."""
        marker = f"MCPPARAM{abs(hash(name)) % 100000}="
        with contextlib.suppress(Exception):
            self.run_vba(
                "Sub Main\n"
                f'ReportInformationToWindow "{marker}" & RestoreParameter("{name}")\n'
                "End Sub\n"
            )
            for entry in reversed(self.messages(limit=15)):
                if marker in entry["text"]:
                    return entry["text"].split(marker, 1)[1].strip()
        return None

    def list_parameters(self) -> dict[str, str]:
        marker = "MCPPARAMLIST="
        with contextlib.suppress(Exception):
            self.run_vba(
                "Sub Main\n"
                "Dim i As Long, s As String, nm As String\n"
                "For i = 0 To GetNumberOfParameters() - 1\n"
                "nm = GetParameterName(i)\n"
                's = s & nm & "=" & RestoreParameter(nm) & vbLf\n'
                "Next i\n"
                f'ReportInformationToWindow "{marker}" & s\n'
                "End Sub\n"
            )
            for entry in reversed(self.messages(limit=15)):
                if marker in entry["text"]:
                    body = entry["text"].split(marker, 1)[1]
                    parsed: dict[str, str] = {}
                    for line in body.replace("\r", "\n").split("\n"):
                        line = line.strip()
                        if "=" in line:
                            key, _, value = line.partition("=")
                            parsed[key.strip()] = value.strip()
                    return parsed
        return {}

    def set_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Change parameters through the CST parameter list (verified mechanism).

        `StoreParameters` + `Rebuild` must run as a `Sub Main` block. The same
        code inside a history block is rejected by CST and can block the Design
        Environment, so it is never generated that way here.
        """
        from .lint import validate_parameter_values

        pairs = validate_parameter_values(parameters)
        names = list(pairs)
        lines = ["Sub Main", f"Dim n(1 To {len(names)}) As String",
                 f"Dim v(1 To {len(names)}) As String"]
        for index, name in enumerate(names, start=1):
            lines.append(f'n({index}) = "{name}"')
            lines.append(f'v({index}) = "{pairs[name]}"')
        lines += ["StoreParameters n, v", "Rebuild", "End Sub"]
        self.run_vba("\n".join(lines) + "\n")
        return {
            "ok": True,
            "changed": {name: self.parameter(name) for name in names},
            "method": "parameter list (StoreParameters + Rebuild in a Sub Main block)",
        }

    def ensure_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Create or update parameters through the parameter list.

        `MakeSureParameterExists` leaves an existing parameter untouched, so this
        is the safe primitive for both "create the parameter block" and "apply a
        design point". It runs as a `Sub Main` block (immediate execution), never
        inside the history tree, which is what CST requires.
        """
        from .lint import validate_parameter_values

        pairs = validate_parameter_values(parameters)
        lines = ["Sub Main"]
        for name, value in pairs.items():
            lines.append(f'MakeSureParameterExists "{name}", "{value}"')
        lines.append("Rebuild")
        lines.append("End Sub")
        self.run_vba("\n".join(lines) + "\n")
        readback = {name: self.parameter(name) for name in pairs}
        # MakeSureParameterExists does not overwrite, so set explicitly when the
        # read-back differs from what was asked for.
        mismatched = {
            name: pairs[name]
            for name, current in readback.items()
            if current is None or str(current).strip() != str(pairs[name]).strip()
        }
        if mismatched:
            return self.set_parameters({**pairs, **mismatched})
        return {
            "ok": True,
            "changed": readback,
            "method": "parameter list (MakeSureParameterExists + Rebuild in a Sub Main block)",
        }


_SESSION: CSTSession | None = None


def session() -> CSTSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = CSTSession()
    return _SESSION
