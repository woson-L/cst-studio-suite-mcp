"""Session, project and environment tools."""
from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path
from typing import Any

from .. import config
from ..registry import ToolRegistry
from ..session import CSTError, session

CATEGORY = "session"

#: A frequency-domain solve needs roughly this much free RAM. Measured on this
#: machine: with ~1.7 GB free CST failed with "Error during construction of
#: pre-conditioner. Not enough memory."
MIN_FREE_RAM_BYTES = 2 * 1024 ** 3

#: Each open 3D project owns one modeler worker of about this size.
MODELER_APPROX_BYTES = 700 * 1024 ** 2


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _free_ram_bytes() -> int | None:
    """Free physical RAM. Windows only; returns None elsewhere."""
    if not sys.platform.startswith("win"):
        return None
    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPhys)
    except Exception:  # noqa: BLE001
        return None


def _cst_worker_count() -> int | None:
    """How many CST worker/DE processes are alive right now."""
    if not sys.platform.startswith("win"):
        return None
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq modeler_AMD64.exe", "/NH"],
            capture_output=True, text=True, timeout=20,
        )
        return sum(1 for line in completed.stdout.splitlines()
                   if "modeler_AMD64.exe" in line)
    except Exception:  # noqa: BLE001
        return None


def memory_report() -> dict[str, Any]:
    """Free RAM and CST worker count, with the risk spelled out for the model."""
    free = _free_ram_bytes()
    workers = _cst_worker_count()
    report: dict[str, Any] = {
        "free_ram_bytes": free,
        "free_ram_gb": round(free / 1024 ** 3, 2) if free else None,
        "open_cst_workers": workers,
        "min_free_ram_gb_for_fd_solve": round(MIN_FREE_RAM_BYTES / 1024 ** 3, 1),
        "approx_ram_per_open_project_gb": round(MODELER_APPROX_BYTES / 1024 ** 3, 2),
    }
    if free is not None and free < MIN_FREE_RAM_BYTES:
        report["warning"] = (
            f"only {report['free_ram_gb']} GB free RAM. A frequency-domain solve needs about "
            f"{report['min_free_ram_gb_for_fd_solve']} GB and will otherwise fail with "
            "'Not enough memory'. Close other applications, and call cst_quit_tool to release "
            "any CST projects left open (each holds about "
            f"{report['approx_ram_per_open_project_gb']} GB)."
        )
    if workers:
        report["note"] = (
            f"{workers} CST worker process(es) are running, holding roughly "
            f"{round(workers * MODELER_APPROX_BYTES / 1024 ** 3, 1)} GB. Each open 3D project "
            "keeps one alive until that project is closed."
        )
    return report


def register_tools(registry: ToolRegistry) -> None:
    s = session

    @registry.tool(
        "cst_health_check_tool", "Check CST install, Python libraries, workspace and running Design Environments.",
        CATEGORY, params={}, returns="environment report with a `ready` flag",
        examples=[{}],
        notes=[
            "Call this first on a new or offline machine.",
            "Also reports free RAM and the number of live CST worker processes, because "
            "each open 3D project holds roughly 700 MB and a frequency-domain solve needs "
            "about 2 GB free; 'Not enough memory' during the solve is usually this.",
        ],
    )
    def health() -> dict[str, Any]:
        info = s().detect()
        ws = config.workspace()
        ev = config.evidence_dir()
        writable = True
        try:
            probe = ws / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception:  # noqa: BLE001
            writable = False
        info["workspace_writable"] = writable
        info["evidence_dir"] = str(ev)
        info["resources"] = memory_report()
        return info

    @registry.tool(
        "cst_detect_tool", "Detect the CST executable, automation libraries and running Design Environments.",
        CATEGORY, params={}, returns="CST detection report",
    )
    def detect() -> dict[str, Any]:
        return s().detect()

    @registry.tool(
        "cst_list_design_environments_tool", "List the PIDs of running CST Design Environments.",
        CATEGORY, params={}, returns="count and pids",
    )
    def list_des() -> dict[str, Any]:
        from ..session import cst_interface

        pids = list(cst_interface().running_design_environments())
        return {"ok": True, "count": len(pids), "pids": pids}

    @registry.tool(
        "cst_connect_tool", "Connect to a running CST Design Environment, optionally launching one.",
        CATEGORY,
        params={"launch_if_needed": "bool", "pid": "int | null"},
        returns="session info after connecting",
        examples=[{"launch_if_needed": True}],
    )
    def connect(launch_if_needed: bool = True, pid: int | None = None) -> dict[str, Any]:
        if pid is not None:
            from ..session import cst_interface

            s()._de = cst_interface().DesignEnvironment.connect(pid)  # noqa: SLF001
            return s().info()
        return s().connect(launch_if_needed=launch_if_needed)

    @registry.tool(
        "cst_project_info_tool", "Report the active project, all open projects and the recent CST messages.",
        CATEGORY, params={}, returns="project metadata and message tail",
        notes=["Read messages_tail after any failure: CST explains itself there."],
    )
    def project_info() -> dict[str, Any]:
        return s().info()

    @registry.tool(
        "cst_new_project_tool", "Create a new CST project and save it into the workspace immediately.",
        CATEGORY,
        params={"project_type": "str", "path": "str | null"},
        examples=[{"project_type": "mws"}],
        returns="session info plus saved_to",
        notes=["project_type: mws, ems, ps, mps, cs, pcbs, ds"],
    )
    def new_project(project_type: str = "mws", path: str | None = None) -> dict[str, Any]:
        return s().new_project(project_type=project_type, path=path)

    @registry.tool(
        "cst_save_project_tool", "Save the active project, optionally to a specific path.",
        CATEGORY, params={"path": "str | null", "overwrite": "bool"},
        examples=[{"path": "C:\\CST_MCP_workspace\\antenna.cst"},
                  {"path": "C:\\CST_MCP_workspace\\antenna.cst", "overwrite": True}],
        returns="{ok, path, overwritten}",
        notes=[
            "CST refuses a save onto an existing project, in one of two ways: 'The "
            "given path already exists <file>', or 'The project directory <dir> "
            "already exists and is non-empty. It would be overwritten.' Saving to the "
            "same path twice in a run (save -> solve -> save) therefore needs "
            "overwrite=True.",
            "overwrite=True passes CST's own allow_overwrite flag. If a project still "
            "occupies that path it is closed first: Model/ and Result/ stay locked "
            "while it is open and CST then fails with a bare 'Failed to save project'. "
            "No dialog is raised and no file is deleted by this server. Verified on "
            "CST 2026.2 - see docs/dev/verification.md.",
            "If the target is already the active project file, the tool saves in place "
            "instead and never closes or deletes anything.",
        ],
    )
    def save_project(path: str | None = None, overwrite: bool = False) -> dict[str, Any]:
        return s().save_project(path=path, overwrite=overwrite)

    @registry.tool(
        "cst_open_project_tool", "Open a .cst project in the connected Design Environment.",
        CATEGORY, params={"path": "str"}, required=["path"],
        examples=[{"path": "C:\\CST_MCP_workspace\\antenna.cst"}],
    )
    def open_project(path: str) -> dict[str, Any]:
        return s().open_project(path)

    @registry.tool(
        "cst_close_project_tool", "Close the active project without quitting CST.",
        CATEGORY, params={},
        returns="{ok, closed, error?}",
        notes=[
            "Only the ACTIVE project is closed. Every other open project keeps its own "
            "~700 MB modeler worker alive; use cst_quit_tool to release them all.",
            "A failed close now reports ok=False with the CST message instead of "
            "silently claiming success.",
        ],
    )
    def close_project() -> dict[str, Any]:
        return s().close_project()

    @registry.tool(
        "cst_quit_tool",
        "Close every open project and release the Design Environment process.",
        CATEGORY, params={},
        returns="{ok, closed_projects, failed_projects, design_environment_released}",
        notes=[
            "Call this at the end of a job. Each open 3D project holds roughly 700 MB in "
            "its own modeler_AMD64 worker, so leaving projects open is what makes the "
            "next solve fail with 'Not enough memory'.",
            "Unlike the previous version this closes ALL projects, not only the active one, "
            "and then closes the Design Environment itself (verified live: the CST process "
            "and its workers all exit).",
        ],
    )
    def quit_all() -> dict[str, Any]:
        return s().quit()

    @registry.tool(
        "cst_messages_tool", "Read the CST message window (INFO / WARNING / ERROR).",
        CATEGORY, params={"limit": "int", "errors_only": "bool"},
        returns="list of {type, text}",
        notes=["This is where the real reason for a failed solve appears."],
    )
    def messages(limit: int = 25, errors_only: bool = False) -> dict[str, Any]:
        if errors_only:
            items = [
                {"type": m["type"], "text": m["text"]}
                for m in s().messages(limit=limit)
                if m["type"].upper().startswith("ERROR") or "error" in m["text"].lower()
            ]
        else:
            items = s().messages(limit=limit)
        return {"ok": True, "count": len(items), "messages": items}

    @registry.tool(
        "cst_workspace_tool", "Report the workspace and evidence folders and what they contain.",
        CATEGORY, params={}, returns="folder paths and file counts",
    )
    def workspace() -> dict[str, Any]:
        ws = config.workspace()
        ev = config.evidence_dir()
        return {
            "ok": True,
            "workspace": str(ws),
            "evidence_dir": str(ev),
            "projects": sorted(p.name for p in ws.glob("*.cst")),
            "evidence_files": sorted(p.name for p in ev.glob("*"))[:50],
        }

    @registry.tool(
        "cst_run_vba_tool", "Execute raw CST VBA immediately (not stored in the history tree).",
        CATEGORY, params={"vba_code": "str"}, required=["vba_code"],
        examples=[{"vba_code": 'ReportInformationToWindow "hello"'}],
        notes=[
            "Use for queries and small fixes. Use cst_add_to_history_tool for model structure.",
            "A Sub Main wrapper is added automatically when the code has none.",
        ],
    )
    def run_vba(vba_code: str) -> dict[str, Any]:
        result = s().run_vba(vba_code)
        result["messages_tail"] = s().messages(limit=6)
        return result

    @registry.tool(
        "cst_add_to_history_tool", "Append one named block to the model history tree (geometry, mesh, solver, ...).",
        CATEGORY, params={"title": "str", "vba_code": "str"}, required=["title", "vba_code"],
        examples=[{"title": "create substrate",
                   "vba_code": 'With Brick\n .Reset\n .Name "substrate"\n .Component "board"\n'
                               ' .Material "FR-4 (lossy)"\n .Xrange "-20","20"\n .Yrange "-15","15"\n'
                               ' .Zrange "-1.6","0"\n .Create\nEnd With'}],
        notes=[
            "Never put StoreParameter/StoreParameters/Rebuild in this block: CST refuses it and can block the session.",
            "The model is rebuilt automatically after the block, so Rebuild is never needed here.",
        ],
        replaces_vba="Model3D.AddToHistory",
    )
    def add_to_history(title: str, vba_code: str) -> dict[str, Any]:
        return s().add_history(title, vba_code)
