#!/usr/bin/env python3
"""Check whether CST-MCP is correctly installed on this computer, and fix the paths.

Answers three questions in order:

  1. Is this machine able to run CST-MCP at all?
       Python version, required packages, the tool modules, the CST installation.
  2. Is MCP itself working?
       Starts the server over stdio, performs the MCP handshake, lists the tools.
       This is what an MCP client (and therefore the model) will do.
  3. Are the paths right for *this* computer?
       CST and workspace folders are located automatically, and `--fix` writes
       them into .env.

Usage
-----
    python check_install.py              # full check, change nothing
    python check_install.py --quick      # skip the CST import / MCP handshake
    python check_install.py --fix        # detect CST paths and write .env
    python check_install.py --fix --workspace "C:\\CST_MCP_workspace"

Exit codes: 0 = ready, 1 = warnings, 2 = problems found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Console output must survive a non-UTF-8 code page (the messages mention
# Chinese filenames). Reconfigure when the API is available, and fall back to
# replacing unencodable characters otherwise.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError, OSError):
        pass

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"

OK = "PASS"
WARN = "WARN"
FAIL = "FAIL"

_results: list[tuple[str, str, str]] = []


def record(level: str, name: str, detail: str = "") -> None:
    _results.append((level, name, detail))
    icon = {OK: "[PASS]", WARN: "[WARN]", FAIL: "[FAIL]"}[level]
    line = f"  {icon} {name}"
    if detail:
        line += f"  {detail}"
    print(line, flush=True)


def section(title: str) -> None:
    print(f"\n== {title} ==", flush=True)


# --------------------------------------------------------------- environment
def parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    # utf-8-sig strips a BOM if present. Without it, a .env saved by an editor that
    # writes a BOM (Notepad does) yields a first key of '\ufeffCST_INSTALL_ROOT',
    # which silently never matches and reports CST_INSTALL_ROOT as unset.
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip().lstrip("\ufeff")] = value.strip().strip('"').strip("'")
    return data


def write_env(path: Path, values: dict[str, str]) -> None:
    """Update keys in .env, preserving comments and unrelated lines."""
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    remaining = dict(values)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    if remaining:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- written by check_install.py --fix ---")
        for key, value in remaining.items():
            out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


# ------------------------------------------------------------- CST discovery
def _version_key(name: str) -> tuple:
    numbers = [int(n) for n in re.findall(r"\d+", name)]
    return tuple(numbers) if numbers else (0,)


def candidate_roots() -> list[Path]:
    """Plausible 'CST Studio Suite <year>' folders on this computer."""
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key in seen or not path.is_dir():
            return
        seen.add(key)
        found.append(path)

    roots: list[Path] = []

    # 1. Drives that exist, most likely first: explicit env, then G..Z, then C..F.
    for letter in ("G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
                   "S", "T", "U", "V", "W", "X", "Y", "Z",
                   "C", "D", "E", "F"):
        drive = Path(f"{letter}:\\")
        if not drive.exists():
            continue
        roots.append(drive / "Program Files")
        roots.append(drive / "Program Files (x86)")
        roots.append(drive)

    # 2. Whatever is already configured.
    for key in ("CST_INSTALL_ROOT", "CST_DESIGN_ENVIRONMENT_EXE"):
        value = os.environ.get(key)
        if value:
            p = Path(value)
            roots.append(p if p.is_dir() else p.parent)

    for root in roots:
        if not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except (PermissionError, OSError):
            continue
        for child in children:
            name = child.name.lower()
            if "cst" in name and "studio" in name and child.is_dir():
                add(child)
    return found


def find_cst() -> list[dict[str, str]]:
    """Return every usable CST installation with its Design Environment exe."""
    installs: list[dict[str, str]] = []
    for root in candidate_roots():
        exe_dir = root / "AMD64"
        exe = None
        for candidate in ("CST DESIGN ENVIRONMENT_AMD64.exe",
                          "CST DESIGN ENVIRONMENT.exe"):
            if (exe_dir / candidate).is_file():
                exe = exe_dir / candidate
                break
        installs.append({
            "root": str(root),
            "exe": str(exe) if exe else "",
            "version": root.name,
        })
    installs.sort(key=lambda item: _version_key(item["version"]), reverse=True)
    return installs


# ------------------------------------------------------------------- checks
def check_python() -> None:
    section("1. Python and packages")
    version = sys.version_info
    if version >= (3, 10):
        record(OK, "python version", f"{version.major}.{version.minor}.{version.micro}")
    elif version >= (3, 8):
        record(WARN, "python version",
               f"{version.major}.{version.minor} - the mcp package needs 3.10+")
    else:
        record(FAIL, "python version", f"{version.major}.{version.minor} is too old")

    try:
        import mcp  # noqa: F401
        record(OK, "package 'mcp'", "importable")
    except ImportError:
        record(FAIL, "package 'mcp'",
               "missing - run: python -m pip install \"mcp>=1.10,<2\"")
    try:
        import pydantic  # noqa: F401
        record(OK, "package 'pydantic'", "importable")
    except ImportError:
        record(FAIL, "package 'pydantic'", "missing - run: python -m pip install pydantic")


def check_packaging() -> None:
    """pyproject must agree with the files on disk.

    setuptools fails the entire build when a declared py-module is absent
    ("file X.py (for module X) not found" -> metadata-generation-failed), which
    makes `pip install .` exit 1. An earlier revision of this file declared five
    modules that belong to the previous package, so this is checked rather than
    trusted.
    """
    section("2b. Packaging metadata")
    pyproject = HERE / "pyproject.toml"
    if not pyproject.is_file():
        record(WARN, "pyproject.toml", "missing - pip install will not work")
        return
    text = pyproject.read_text(encoding="utf-8")
    block = re.search(r"py-modules\s*=\s*\[(.*?)\]", text, re.DOTALL)
    declared = re.findall(r'"([^"]+)"', block.group(1)) if block else []
    actual = sorted(p.stem for p in HERE.glob("*.py") if p.name != "check_install.py")
    missing = [m for m in declared if not (HERE / f"{m}.py").is_file()]
    undeclared = [m for m in actual if m not in declared]
    if missing:
        record(FAIL, "py-modules declared but absent", ", ".join(missing)
               + " - pip install . will fail with 'file X.py not found'")
    else:
        record(OK, "py-modules", f"{len(declared)} declared, all present")
    if undeclared:
        record(WARN, "top-level modules not declared", ", ".join(undeclared))
    else:
        record(OK, "top-level modules", "all declared in pyproject.toml")


def check_files() -> None:
    section("2. CST-MCP files")
    record(OK if (HERE / "mcp_server.py").is_file() else FAIL,
           "mcp_server.py", str(HERE / "mcp_server.py"))
    tools_dir = HERE / "cst_mcp" / "tools"
    modules = sorted(p.name for p in tools_dir.glob("*_tools.py")) if tools_dir.is_dir() else []
    record(OK if modules else FAIL, "tool modules", f"{len(modules)} found")
    for helper in ("cst_mcp/session.py", "cst_mcp/registry.py", "cst_mcp/lint.py",
                   "cst_mcp/config.py", "cst_mcp/vba/geometry.py"):
        record(OK if (HERE / helper).is_file() else FAIL, helper)
    # Offline test runners. These are what a fresh machine uses to prove the copy
    # arrived intact, so a missing one is worth reporting rather than ignoring.
    for runner in ("smoke_registry.py", "check_mcp_compliance.py",
                   "check_self_description.py", "check_skill_tool_refs.py",
                   "check_skill_layout.py", "check_docs_consistency.py",
                   "test_audit_regressions.py", "test_port_info_verdict.py",
                   "verify_live.py", "verify_fixes_live.py", "run_123_task.py"):
        path = HERE / "tests" / runner
        record(OK if path.is_file() else WARN, f"tests/{runner}",
               "" if path.is_file() else "missing - copy the folder completely")
    for doc in ("README.md", "docs/start/install.md", "docs/start/install-via-agent.md", "docs/mcp_tools.json",
                "skills/cst-studio-suite-mcp/SKILL.md",
                "skills/cst-studio-suite-mcp/metadata.json",
                "skills/cst-studio-suite-mcp/agents/openai.yaml",
                "skills/cst2026-simulation-execution/SKILL.md",
                "skills/cst2026-simulation-execution/metadata.json",
                "skills/cst2026-simulation-execution/agents/openai.yaml",
                "tests/evidence/known_failures.md"):
        path = HERE / doc
        record(OK if path.is_file() else WARN, doc,
               "" if path.is_file() else "missing")
    # Each skill is a directory: a SKILL.md router plus its references/. A skill
    # copied without references/ still loads but points at files that are not there,
    # which is exactly the partial copy this check exists to catch.
    for skill, expected_refs in (("cst-studio-suite-mcp", 7),
                                 ("cst2026-simulation-execution", 4)):
        refs = HERE / "skills" / skill / "references"
        found = len(list(refs.glob("*.md"))) if refs.is_dir() else 0
        record(OK if found == expected_refs else WARN,
               f"skills/{skill}/references",
               f"{found}/{expected_refs} files"
               + ("" if found == expected_refs else " - the folder copy is incomplete"))


def check_env(quick: bool) -> dict[str, str]:
    section("3. Configuration (.env)")
    env = parse_env(ENV_FILE)
    if not ENV_FILE.is_file():
        record(FAIL, ".env",
               "missing - copy .env.example to .env and set the CST paths "
               "(see docs/start/install.md step 3)")
    else:
        record(OK, ".env", str(ENV_FILE))

    for key in ("CST_INSTALL_ROOT", "CST_DESIGN_ENVIRONMENT_EXE"):
        value = env.get(key, "")
        if not value:
            record(FAIL, key,
                   "not set - edit .env, or run: python check_install.py --fix")
        elif "<" in value or ">" in value:
            record(FAIL, key, f"{value}  -> still a placeholder from .env.example")
        elif not Path(value).exists():
            record(FAIL, key, f"{value}  -> does not exist on this computer")
        else:
            record(OK, key, value)

    for key in ("CST_MCP_WORKSPACE", "CST_MCP_EVIDENCE"):
        value = env.get(key, "")
        if not value:
            record(WARN, key, "not set - defaults to a folder next to mcp_server.py")
            continue
        if "<" in value or ">" in value:
            record(FAIL, key, f"{value}  -> still a placeholder from .env.example")
            continue
        try:
            Path(value).mkdir(parents=True, exist_ok=True)
            probe = Path(value) / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            record(OK, key, f"{value} (writable)")
        except Exception as exc:  # noqa: BLE001
            record(FAIL, key, f"{value} is not writable: {exc}")

    exe = env.get("CST_DESIGN_ENVIRONMENT_EXE", "")
    if exe and Path(exe).is_file():
        record(OK, "CST executable", Path(exe).name)

    if not quick:
        try:
            sys.path.insert(0, str(HERE))
            from cst_mcp import config  # noqa: PLC0415

            config.ensure_cst_paths()
            import cst.interface  # noqa: F401,PLC0415
            import cst.results  # noqa: F401,PLC0415
            record(OK, "cst.interface + cst.results", "importable")
        except Exception as exc:  # noqa: BLE001
            record(FAIL, "cst.interface / cst.results",
                   f"{type(exc).__name__}: {exc}")
    return env


def check_registry() -> int:
    section("4. Tool registry")
    try:
        sys.path.insert(0, str(HERE))
        import mcp_server  # noqa: PLC0415

        count = len(mcp_server.registry)
        record(OK, "tools registered", f"{count} tools")
        grouped = mcp_server.registry.by_category()
        record(OK, "categories", ", ".join(sorted(grouped)))
        names = mcp_server.registry.names()
        dupes = sorted({n for n in names if names.count(n) > 1})
        record(OK if not dupes else FAIL, "duplicate names", str(dupes) if dupes else "none")
        failed = mcp_server.EXTENSION_REPORT.get("failed") or []
        record(OK if not failed else WARN, "module discovery",
               f"{len(mcp_server.EXTENSION_REPORT.get('loaded', []))} modules loaded"
               + (f", {len(failed)} failed: {failed}" if failed else ""))
        return count
    except Exception as exc:  # noqa: BLE001
        record(FAIL, "registry", f"{type(exc).__name__}: {exc}")
        return 0


def check_mcp_handshake(timeout: float = 90.0) -> None:
    section("5. MCP handshake (what the model's client does)")
    try:
        import anyio  # noqa: PLC0415
        from mcp import ClientSession, StdioServerParameters  # noqa: PLC0415
        from mcp.client.stdio import stdio_client  # noqa: PLC0415
    except ImportError as exc:
        record(FAIL, "mcp client libraries", f"{exc}")
        return

    async def run() -> None:
        params = StdioServerParameters(
            command=sys.executable, args=[str(HERE / "mcp_server.py")], cwd=str(HERE)
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                record(OK, "initialize", f"server={init.serverInfo.name}")
                record(OK, "protocol version", str(init.protocolVersion))
                record(OK if init.instructions else WARN, "instructions advertised",
                       (init.instructions or "")[:60].replace("\n", " ") or "none")
                tools = (await session.list_tools()).tools
                record(OK if tools else FAIL, "tools/list", f"{len(tools)} tools")
                names = [t.name for t in tools]
                record(OK if len(names) == len(set(names)) else FAIL,
                       "unique tool names", f"{len(set(names))} unique")
                missing = [t.name for t in tools if not (t.description or "").strip()]
                record(OK if not missing else WARN, "descriptions",
                       "all present" if not missing else f"missing on {missing[:3]}")
                for name in ("cst_health_check_tool", "cst_set_solver_tool",
                             "cst_set_frequency_range_tool", "cst_run_solver_tool"):
                    record(OK if name in names else FAIL, f"tool {name}",
                           "available" if name in names else "MISSING")

    try:
        anyio.run(run)
    except BaseException as exc:  # noqa: BLE001
        record(FAIL, "MCP handshake", f"{type(exc).__name__}: {exc}")


def check_cst_live(timeout: float = 120.0) -> None:
    section("6. CST availability (cst_connect_tool + cst_health_check_tool)")
    try:
        import anyio  # noqa: PLC0415
        from mcp import ClientSession, StdioServerParameters  # noqa: PLC0415
        from mcp.client.stdio import stdio_client  # noqa: PLC0415
    except ImportError:
        return

    async def run() -> None:
        params = StdioServerParameters(
            command=sys.executable, args=[str(HERE / "mcp_server.py")], cwd=str(HERE)
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def call(tool: str):
                    res = await session.call_tool(tool, {}, read_timeout_seconds=None)
                    text = "\n".join(getattr(b, "text", "") or "" for b in res.content)
                    try:
                        return bool(res.isError), json.loads(text)
                    except json.JSONDecodeError:
                        return bool(res.isError), text

                err, data = await call("cst_health_check_tool")
                if err or not isinstance(data, dict):
                    record(FAIL, "cst_health_check_tool", str(data)[:150])
                    return
                record(OK, "cst_health_check_tool",
                       f"ready={data.get('ready')} interface={data.get('cst_interface_importable')} "
                       f"results={data.get('cst_results_importable')}")
                if not data.get("ready"):
                    record(FAIL, "CST libraries", str(data.get("cst_interface_error", ""))[:150])
                    return

                err, info = await call("cst_list_design_environments_tool")
                if not err and isinstance(info, dict):
                    record(OK, "cst_list_design_environments_tool",
                           f"count={info.get('count')}")

                err, conn = await call("cst_connect_tool")
                if err:
                    record(WARN, "cst_connect_tool", str(conn)[:150])
                else:
                    record(OK, "cst_connect_tool",
                           f"pid={conn.get('design_environment_pid') if isinstance(conn, dict) else '?'}")

    try:
        anyio.run(run)
    except BaseException as exc:  # noqa: BLE001
        record(WARN, "CST live check", f"{type(exc).__name__}: {exc}")


def _usable_path(value: str) -> bool:
    """True when a configured path is a real, absolute path that exists.

    Placeholders left in .env.example (e.g. '<drive>:\\CST_MCP_workspace') and
    relative paths are treated as not-configured, so --fix replaces them.
    """
    if not value or "<" in value or ">" in value:
        return False
    try:
        path = Path(value)
    except (OSError, ValueError):
        return False
    if not path.is_absolute():
        return False
    return path.exists()


def do_fix(workspace: str | None) -> int:
    section("Fixing configuration")
    installs = find_cst()
    if not installs:
        record(FAIL, "CST installation",
               "none found. Set CST_INSTALL_ROOT by hand in .env")
        return 2

    chosen = next((i for i in installs if i["exe"]), installs[0])
    record(OK, "CST found", chosen["root"])
    if chosen["exe"]:
        record(OK, "Design Environment", chosen["exe"])
    else:
        record(WARN, "Design Environment exe",
               "not found under <root>\\AMD64 - check the installation")
    if len(installs) > 1:
        record(WARN, "other installs",
               "; ".join(i["root"] for i in installs[1:4]))

    if not ENV_FILE.is_file():
        example = HERE / ".env.example"
        if example.is_file():
            ENV_FILE.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    values = {
        "CST_INSTALL_ROOT": chosen["root"],
        "CST_DESIGN_ENVIRONMENT_EXE": chosen["exe"] or "",
    }
    existing = parse_env(ENV_FILE)
    if workspace:
        values["CST_MCP_WORKSPACE"] = workspace
        values["CST_MCP_EVIDENCE"] = str(Path(workspace) / "evidence")
    elif not _usable_path(existing.get("CST_MCP_WORKSPACE", "")):
        # Not configured yet, or still holding a placeholder: derive it from the
        # CST drive so the workspace lands on the same disk as CST.
        drive = Path(chosen["root"]).drive or "C:"
        values["CST_MCP_WORKSPACE"] = f"{drive}\\CST_MCP_workspace"
        values["CST_MCP_EVIDENCE"] = f"{drive}\\CST_MCP_workspace\\evidence"

    write_env(ENV_FILE, values)
    record(OK, ".env written", str(ENV_FILE))
    print()
    for key, value in values.items():
        print(f"    {key}={value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether CST-MCP is installed correctly on this computer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python check_install.py                 full check (uses CST)\n"
               "  python check_install.py --quick         no CST, no MCP handshake\n"
               "  python check_install.py --fix           detect CST and write .env\n"
               "  python check_install.py --fix --workspace \"C:\\\\CST_MCP_workspace\"\n",
    )
    parser.add_argument("--quick", action="store_true",
                        help="skip the CST import and the MCP handshake")
    parser.add_argument("--fix", action="store_true",
                        help="detect the CST installation and write .env")
    parser.add_argument("--workspace", help="workspace folder to record in .env")
    parser.add_argument("--list-installs", action="store_true",
                        help="only list the CST installations found on this computer")
    args = parser.parse_args(argv)

    print("== CST-MCP install check ==")
    print(f"folder   : {HERE}")
    print(f"python   : {sys.executable}")

    if args.list_installs:
        section("CST installations found")
        installs = find_cst()
        if not installs:
            print("  none found")
            return 2
        for item in installs:
            print(f"  root : {item['root']}")
            print(f"  exe  : {item['exe'] or '(not found)'}")
        return 0

    if args.fix:
        rc = do_fix(args.workspace)
        if rc:
            return rc

    check_python()
    check_files()
    check_packaging()
    env = check_env(args.quick)
    check_registry()
    if not args.quick:
        check_mcp_handshake()
        if env.get("CST_DESIGN_ENVIRONMENT_EXE"):
            check_cst_live(timeout=120.0)

    fails = [r for r in _results if r[0] == FAIL]
    warns = [r for r in _results if r[0] == WARN]
    section("Summary")
    print(f"  passed : {len([r for r in _results if r[0] == OK])}")
    print(f"  warning: {len(warns)}")
    print(f"  failed : {len(fails)}")
    if fails:
        print("\n  Problems:")
        for _, name, detail in fails:
            print(f"    - {name}: {detail}")
    if warns:
        print("\n  Warnings:")
        for _, name, detail in warns:
            print(f"    - {name}: {detail}")

    if fails:
        print("\nRESULT: NOT READY - fix the problems above")
        return 2
    if warns:
        print("\nRESULT: READY (with warnings)")
        return 1
    print("\nRESULT: READY - point your MCP client at this folder:")
    print(f"  command = {sys.executable}")
    print(f"  args    = [\"{HERE / 'mcp_server.py'}\"]")
    print(f"  cwd     = {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
