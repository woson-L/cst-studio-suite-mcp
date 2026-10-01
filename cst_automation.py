from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
from typing import Any

from cst_schematic import SchematicEndpoint, wrap_sub_main


DEFAULT_CST_EXE = r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
DEFAULT_CST_ROOT = r"C:\Program Files\CST Studio Suite 2026"
_CST_PATHS_READY = False


class CSTImportError(RuntimeError):
    """Raised when the CST Python modules are not importable."""


def _jsonable(value: Any) -> Any:
    """Convert common CST/Python values into JSON-safe structures."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "tolist"):
        try:
            return _jsonable(value.tolist())
        except Exception:
            pass
    return repr(value)


def _load_cst_module(name: str) -> Any:
    _ensure_cst_paths()
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - depends on local CST install
        raise CSTImportError(
            f"Cannot import {name!r}. Run this MCP with the CST bundled Python "
            r"(for example C:\Program Files\CST Studio Suite 2026\Python\python.exe) "
            "or set PYTHONPATH to CST's python_cst_libraries."
        ) from exc


def _cst_root() -> Path:
    configured_root = os.environ.get("CST_INSTALL_ROOT")
    if configured_root:
        return Path(configured_root)
    configured_exe = Path(os.environ.get("CST_DESIGN_ENVIRONMENT_EXE", DEFAULT_CST_EXE))
    if configured_exe.name:
        return configured_exe.parent.parent
    return Path(DEFAULT_CST_ROOT)


def _ensure_cst_paths() -> None:
    """Expose CST Python packages and native DLLs to non-CST Python runtimes."""
    global _CST_PATHS_READY
    if _CST_PATHS_READY:
        return
    root = _cst_root()
    python_lib = root / "AMD64" / "python_cst_libraries"
    amd64_dir = root / "AMD64"
    if python_lib.exists():
        python_lib_str = str(python_lib)
        if python_lib_str not in os.sys.path:
            os.sys.path.insert(0, python_lib_str)
    if amd64_dir.exists():
        amd64_str = str(amd64_dir)
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if amd64_str not in path_parts:
            os.environ["PATH"] = amd64_str + os.pathsep + os.environ.get("PATH", "")
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            with contextlib.suppress(Exception):
                add_dll_directory(amd64_str)
    _CST_PATHS_READY = True


def _optional_call(obj: Any, method: str, *args: Any, **kwargs: Any) -> Any:
    value = getattr(obj, method, None)
    if value is None:
        return None
    if callable(value):
        return value(*args, **kwargs)
    return value


class CSTSessionManager:
    """Stateful controller around cst.interface and cst.results."""

    def __init__(self) -> None:
        self.de: Any | None = None
        self.project: Any | None = None

    @property
    def ci(self) -> Any:
        return _load_cst_module("cst.interface")

    @property
    def results_module(self) -> Any:
        return _load_cst_module("cst.results")

    def detect_environment(self) -> dict[str, Any]:
        cst_exe = os.environ.get("CST_DESIGN_ENVIRONMENT_EXE", DEFAULT_CST_EXE)
        info: dict[str, Any] = {
            "cst_exe": cst_exe,
            "cst_exe_exists": Path(cst_exe).exists(),
            "cst_install_root": str(_cst_root()),
            "python_executable": os.sys.executable,
        }
        try:
            ci = self.ci
            info["cst_interface_importable"] = True
            info["running_design_environments"] = list(ci.running_design_environments())
        except Exception as exc:
            info["cst_interface_importable"] = False
            info["error"] = str(exc)
        try:
            results = self.results_module
            info["cst_results_importable"] = True
            version_info = getattr(results, "get_version_info", None)
            if callable(version_info):
                info["cst_results_version"] = _jsonable(version_info())
        except Exception as exc:
            info["cst_results_importable"] = False
            info["results_error"] = str(exc)
        return info

    def list_running(self) -> dict[str, Any]:
        pids = list(self.ci.running_design_environments())
        return {"count": len(pids), "pids": pids}

    def connect(self, pid_or_address: int | str | None = None, launch_if_needed: bool = False) -> dict[str, Any]:
        ci = self.ci
        if pid_or_address not in (None, ""):
            self.de = ci.DesignEnvironment.connect(pid_or_address)
        elif launch_if_needed:
            self.de = ci.DesignEnvironment.connect_to_any_or_new()
        else:
            self.de = ci.DesignEnvironment.connect_to_any()
        self.project = None
        return self.get_project_info()

    def launch_new(self, options: list[str] | None = None) -> dict[str, Any]:
        self.de = self.ci.DesignEnvironment.new(options=options)
        self.project = None
        return self.get_project_info()

    def _require_de(self) -> Any:
        if self.de is None:
            self.connect(launch_if_needed=False)
        return self.de

    def _require_project(self) -> Any:
        if self.project is not None:
            return self.project
        de = self._require_de()
        self.project = de.active_project()
        return self.project

    def active_project(self) -> dict[str, Any]:
        self.project = self._require_de().active_project()
        return self.get_project_info()

    def open_project(self, path: str) -> dict[str, Any]:
        if not path.strip():
            raise ValueError("path must not be empty")
        cst_path = Path(path).expanduser()
        if not cst_path.exists():
            raise FileNotFoundError(str(cst_path))
        self.project = self._require_de().open_project(str(cst_path))
        return self.get_project_info()

    def new_project(self, project_type: str = "mws") -> dict[str, Any]:
        de = self._require_de()
        normalized = project_type.strip().lower()
        factory_name = {
            "mws": "new_mws",
            "microwave": "new_mws",
            "ems": "new_ems",
            "em": "new_ems",
            "ps": "new_ps",
            "particle": "new_ps",
            "mps": "new_mps",
            "multiphysics": "new_mps",
            "cs": "new_cs",
            "cable": "new_cs",
            "pcbs": "new_pcbs",
            "pcb": "new_pcbs",
            "ds": "new_ds",
            "designstudio": "new_ds",
        }.get(normalized)
        if factory_name is None:
            raise ValueError("project_type must be one of mws, ems, ps, mps, cs, pcbs, ds")
        self.project = getattr(de, factory_name)()
        return self.get_project_info()

    def get_project_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "connected": self.de is not None,
            "design_environment_pid": None,
            "has_active_project": False,
            "open_projects": [],
            "active_project": None,
            "messages_tail": [],
        }
        de = self.de
        if de is None:
            return info
        info["design_environment_pid"] = _optional_call(de, "pid")
        with contextlib.suppress(Exception):
            info["open_projects"] = list(de.list_open_projects())
        with contextlib.suppress(Exception):
            info["has_active_project"] = bool(de.has_active_project())
        prj = self.project
        if prj is None:
            with contextlib.suppress(Exception):
                prj = de.active_project()
        if prj is not None:
            info["active_project"] = self._project_metadata(prj)
            with contextlib.suppress(Exception):
                messages = prj.get_messages()
                info["messages_tail"] = _jsonable(messages[-20:] if isinstance(messages, list) else messages)
        return info

    def _project_metadata(self, prj: Any) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for method in ("filename", "folder", "project_type"):
            with contextlib.suppress(Exception):
                data[method] = _jsonable(getattr(prj, method)())
        for attr in ("model3d", "schematic", "pcbs"):
            data[f"has_{attr}"] = hasattr(prj, attr)
        return data

    def save_project(self, path: str | None = None) -> dict[str, Any]:
        prj = self._require_project()
        if path and path.strip():
            prj.save(path.strip())
        else:
            prj.save()
        return self.get_project_info()

    def _require_schematic(self) -> Any:
        prj = self._require_project()
        schematic = getattr(prj, "schematic", None)
        if schematic is None:
            raise RuntimeError("Active CST project does not expose a Design Studio schematic interface.")
        return schematic

    def new_schematic_project(self, path: str | None = None) -> dict[str, Any]:
        self.new_project(project_type="ds")
        if path and path.strip():
            self.save_project(path=path)
        return self.get_project_info()

    def schematic_add_to_history(self, title: str, vba_code: str) -> dict[str, Any]:
        # CST Design Studio does not expose a history tree like 3D modeling; execute
        # a named VBA macro and report the title through the DS message window.
        if not title.strip():
            raise ValueError("title must not be empty")
        code = f'ReportInformationToWindow("MCP schematic step: {title.strip()}")\n{vba_code}'
        return self.schematic_execute_vba(code)

    def schematic_execute_vba(self, vba_code: str) -> dict[str, Any]:
        schematic = self._require_schematic()
        code = wrap_sub_main(vba_code)
        schematic.execute_vba_code(code)
        return {"ok": True}

    def schematic_run_simulation(self, task_name: str | None = None) -> dict[str, Any]:
        schematic = self._require_schematic()
        if task_name and task_name.strip():
            schematic.SimulationTask.Reset()
            schematic.SimulationTask.Name(task_name.strip())
            schematic.SimulationTask.Update()
        else:
            schematic.UpdateResults()
        return {"ok": True, "project": self._project_metadata(self._require_project())}

    def schematic_export_touchstone(
        self,
        tree_item: str,
        filename_without_extension: str,
        impedance: float | str = 50.0,
    ) -> dict[str, Any]:
        if not tree_item.strip():
            raise ValueError("tree_item must not be empty")
        if not filename_without_extension.strip():
            raise ValueError("filename_without_extension must not be empty")
        schematic = self._require_schematic()
        ok = schematic.TouchstoneExport(tree_item.strip(), filename_without_extension.strip(), str(impedance))
        return {
            "ok": bool(ok),
            "tree_item": tree_item.strip(),
            "filename_without_extension": filename_without_extension.strip(),
            "impedance": str(impedance),
        }

    def add_to_history(self, title: str, vba_code: str) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("title must not be empty")
        if not vba_code.strip():
            raise ValueError("vba_code must not be empty")
        model3d = self._require_project().model3d
        model3d.add_to_history(title.strip(), vba_code)
        return {"ok": True, "title": title.strip()}

    def execute_vba(self, vba_code: str) -> dict[str, Any]:
        if not vba_code.strip():
            raise ValueError("vba_code must not be empty")
        model3d = self._require_project().model3d
        code = vba_code if "sub main" in vba_code.lower() else f"Sub Main\n{vba_code}\nEnd Sub"
        model3d._execute_vba_code(code)
        return {"ok": True}

    def run_solver(self) -> dict[str, Any]:
        model3d = self._require_project().model3d
        model3d.run_solver()
        return {"ok": True, "project": self._project_metadata(self._require_project())}

    def run_python(self, code: str) -> dict[str, Any]:
        if not code.strip():
            raise ValueError("code must not be empty")
        stdout = io.StringIO()
        stderr = io.StringIO()
        namespace: dict[str, Any] = {
            "manager": self,
            "de": self.de,
            "prj": self.project,
            "project": self.project,
            "result": None,
        }
        if self.project is not None:
            namespace["model3d"] = getattr(self.project, "model3d", None)
            namespace["schematic"] = getattr(self.project, "schematic", None)
            namespace["SchematicEndpoint"] = SchematicEndpoint
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compile(code, "<cst-mcp-run-python>", "exec"), namespace, namespace)
        except Exception as exc:
            return {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
            }
        if namespace.get("de") is not None:
            self.de = namespace["de"]
        if namespace.get("prj") is not None:
            self.project = namespace["prj"]
        return {
            "ok": True,
            "result": _jsonable(namespace.get("result")),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }

    def _result_project_path(self, cst_file: str | None) -> str:
        if cst_file and cst_file.strip():
            return cst_file.strip()
        prj = self._require_project()
        filename = prj.filename()
        if not filename:
            raise RuntimeError("Active CST project has no filename yet. Save it or pass cst_file.")
        return filename

    def _result_module(self, cst_file: str | None, module: str) -> Any:
        path = self._result_project_path(cst_file)
        pp = self.results_module.ProjectFile(path, allow_interactive=True)
        if module.lower() in {"3d", "model3d", "mws"}:
            return pp.get_3d()
        if module.lower() in {"schematic", "ds"}:
            return pp.get_schematic()
        raise ValueError("module must be '3d' or 'schematic'")

    def list_results(self, cst_file: str | None = None, module: str = "3d") -> dict[str, Any]:
        result_module = self._result_module(cst_file, module)
        items = list(result_module.get_tree_items())
        return {"count": len(items), "items": items}

    def read_1d_result(
        self,
        tree_path: str,
        cst_file: str | None = None,
        module: str = "3d",
        max_points: int = 2000,
    ) -> dict[str, Any]:
        if not tree_path.strip():
            raise ValueError("tree_path must not be empty")
        result_module = self._result_module(cst_file, module)
        item = result_module.get_result_item(tree_path.strip())
        data = item.get_data()
        length = len(data) if hasattr(data, "__len__") else None
        rows = list(data[:max_points]) if hasattr(data, "__getitem__") else list(data)
        return {
            "tree_path": tree_path.strip(),
            "title": _optional_call(item, "title"),
            "xlabel": _optional_call(item, "xlabel"),
            "ylabel": _optional_call(item, "ylabel"),
            "length": length,
            "returned_points": len(rows),
            "truncated": bool(length is not None and length > len(rows)),
            "data": _jsonable(rows),
        }

    def export_touchstone(
        self,
        filename: str,
        impedance: float = 50.0,
        export_type: str = "S",
        data_format: str = "RI",
        frequency_range: str = "Full",
    ) -> dict[str, Any]:
        if not filename.strip():
            raise ValueError("filename must not be empty")
        export_touchstone = importlib.import_module("cst.post_processing.s_parameters").export_touchstone
        export_touchstone(
            self._require_project(),
            filename.strip(),
            impedance=impedance,
            export_type=export_type,
            format=data_format,
            frequency_range=frequency_range,
        )
        return {"ok": True, "filename": filename.strip()}


def dumps(data: Any) -> str:
    return json.dumps(_jsonable(data), ensure_ascii=False, indent=2)
