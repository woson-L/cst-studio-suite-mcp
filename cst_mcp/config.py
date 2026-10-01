"""Configuration, filesystem layout and CST path resolution for the CST MCP.

Everything is driven by a `.env` file next to this package, so the server works
on a machine with no network access and no pre-set environment variables.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

DEFAULT_CST_ROOT = r"C:\Program Files\CST Studio Suite 2026"
DEFAULT_CST_EXE = r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"

_ENV_LOADED = False


def load_env(path: Path | None = None) -> dict[str, str]:
    """Load a .env file without requiring python-dotenv.

    Existing process environment variables always win, so an MCP client that
    passes an explicit `env` block still takes precedence.
    """
    global _ENV_LOADED
    loaded: dict[str, str] = {}
    candidates: list[Path] = []
    if path:
        candidates.append(path)
    else:
        candidates.extend([PROJECT_ROOT / ".env", PACKAGE_ROOT / ".env"])
    for candidate in candidates:
        if not candidate or not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    _ENV_LOADED = True
    return loaded


def cst_root() -> Path:
    root = os.environ.get("CST_INSTALL_ROOT")
    if root:
        return Path(root).expanduser()
    exe = os.environ.get("CST_DESIGN_ENVIRONMENT_EXE", DEFAULT_CST_EXE)
    return Path(exe).expanduser().parent.parent


def cst_exe() -> Path:
    return Path(os.environ.get("CST_DESIGN_ENVIRONMENT_EXE", DEFAULT_CST_EXE)).expanduser()


def workspace() -> Path:
    """Writable folder for projects created through the MCP."""
    configured = os.environ.get("CST_MCP_WORKSPACE")
    root = Path(configured).expanduser() if configured else PROJECT_ROOT / "cst_workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def evidence_dir() -> Path:
    """Writable folder for exported evidence."""
    configured = os.environ.get("CST_MCP_EVIDENCE")
    root = Path(configured).expanduser() if configured else workspace() / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def quiet() -> bool:
    return os.environ.get("CST_MCP_QUIET", "0").strip() not in {"", "0", "false", "False"}


def resolve_path(value: str | os.PathLike[str], *, base: Path | None = None) -> Path:
    """Resolve a user-supplied path, treating relative paths as workspace-relative."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base or workspace()) / path


def ensure_cst_paths() -> None:
    """Expose CST's Python packages and native DLLs to a non-CST Python runtime."""
    root = cst_root()
    python_lib = root / "AMD64" / "python_cst_libraries"
    amd64 = root / "AMD64"
    if python_lib.is_dir() and str(python_lib) not in os.sys.path:
        os.sys.path.insert(0, str(python_lib))
    if amd64.is_dir():
        parts = os.environ.get("PATH", "").split(os.pathsep)
        if str(amd64) not in parts:
            os.environ["PATH"] = str(amd64) + os.pathsep + os.environ.get("PATH", "")
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            with contextlib.suppress(Exception):
                add_dll_directory(str(amd64))


load_env()
