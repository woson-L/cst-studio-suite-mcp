"""Check the server against MCP protocol expectations.

Verifies the parts of the MCP specification this server is responsible for:
  * stdio transport with a clean JSON-RPC handshake
  * server name / instructions advertised in `initialize`
  * tools/list: unique names, non-empty descriptions, object-rooted input schemas
  * tools/call: structured content, and a proper MCP error for bad input
  * invalid arguments are rejected by schema validation, not by crashing

Does not need CST to be running beyond what the tool calls themselves require.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Derived from this file, so the check runs from any clone and any interpreter.
# It used to hard-code one machine's package folder and virtual-environment
# python, which made it unrunnable everywhere else (including CI).
PKG = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
OUT = PKG / "tests" / "mcp_compliance.json"

results: dict[str, object] = {}


def check(name: str, ok: bool, detail: str = "") -> None:
    results[name] = {"ok": bool(ok), "detail": str(detail)[:400]}
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {str(detail)[:150]}")


async def call(session: ClientSession, tool: str, args: dict | None = None, timeout: int = 60):
    try:
        res = await session.call_tool(tool, args or {},
                                      read_timeout_seconds=timedelta(seconds=timeout))
    except Exception as exc:  # noqa: BLE001
        return True, f"RAISED {type(exc).__name__}: {exc}", None
    text = "\n".join(getattr(b, "text", "") or "" for b in res.content)
    return bool(res.isError), text, res


async def run_checks(session: ClientSession) -> None:
    init = await session.initialize()
    check("initialize_handshake", init is not None,
          f"server={init.serverInfo.name} version={init.serverInfo.version}")
    check("server_name_reported", bool(init.serverInfo.name), init.serverInfo.name)
    check("protocol_version", bool(init.protocolVersion), init.protocolVersion)
    # `instructions` is advertised on the InitializeResult, not on the session.
    howto = getattr(init, "instructions", None)
    check("instructions_advertised", bool(howto),
          (howto or "")[:110].replace("\n", " "))

    tools = (await session.list_tools()).tools
    names = [t.name for t in tools]
    check("tools_listed", len(tools) >= 60, f"{len(tools)} tools")
    dupes = sorted({n for n in names if names.count(n) > 1})
    check("tool_names_unique", not dupes, f"duplicates: {dupes}")
    no_desc = [t.name for t in tools if not (t.description or "").strip()]
    check("all_tools_have_description", not no_desc, f"missing: {no_desc[:5]}")
    bad_prefix = [n for n in names if not n.startswith("cst_")]
    check("tool_naming_convention", not bad_prefix, f"off-pattern: {bad_prefix[:5]}")

    bad_schema = []
    for t in tools:
        schema = t.inputSchema or {}
        if schema.get("type") != "object":
            bad_schema.append(f"{t.name}: type={schema.get('type')}")
        elif "properties" not in schema:
            bad_schema.append(f"{t.name}: no properties")
    check("input_schemas_object_rooted", not bad_schema, "; ".join(bad_schema[:4]))
    check("no_whitespace_in_names",
          not [n for n in names if n != n.strip()], "clean")

    err, text, res = await call(session, "cst_list_mcp_tools_tool")
    check("tools_call_returns_json", (not err) and text.strip().startswith("{"),
          text[:90].replace("\n", " "))
    check("structured_content_present",
          getattr(res, "structuredContent", None) is not None,
          "structuredContent returned" if getattr(res, "structuredContent", None)
          else "no structuredContent")

    err, text, _ = await call(session, "cst_does_not_exist_tool")
    check("unknown_tool_is_error", err, text[:110].replace("\n", " "))

    err, text, _ = await call(session, "cst_create_brick_tool",
                              {"component": 1, "name": 2})
    check("invalid_args_rejected", err, text[:110].replace("\n", " "))

    err, text, _ = await call(session, "cst_add_to_history_tool",
                              {"title": "guard",
                               "vba_code": 'StoreParameter "a", "1"'})
    check("tool_error_is_mcp_error",
          err and "storeparameter" in text.lower(), text[:130].replace("\n", " "))

    # read-only metadata tools must work without any CST session
    err, text, _ = await call(session, "cst_tool_manifest_tool")
    check("manifest_tool_works", (not err) and '"tool_count"' in text, text[:90])
    err, text, _ = await call(session, "cst_runtime_list_tools_tool")
    check("runtime_bridge_works", not err, text[:90].replace("\n", " "))


async def main() -> None:
    env = dict(os.environ)
    env["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
    env["CST_DESIGN_ENVIRONMENT_EXE"] = (
        r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe")
    env["CST_MCP_WORKSPACE"] = str(Path(tempfile.gettempdir()) / "cst_mcp_verify" / "workspace")
    env["CST_MCP_EVIDENCE"] = str(Path(tempfile.gettempdir()) / "cst_mcp_verify" / "evidence")

    params = StdioServerParameters(command=str(PY), args=[str(PKG / "mcp_server.py")],
                                   env=env, cwd=str(PKG))
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await run_checks(session)
    except BaseException as exc:  # noqa: BLE001
        import traceback
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # BaseExceptionGroup hides the real cause; flatten it.
        subs = getattr(exc, "exceptions", None)
        if subs:
            detail += "\n--- sub-exceptions ---\n"
            def walk(items, depth=0):
                out = []
                for item in items:
                    inner = getattr(item, "exceptions", None)
                    if inner:
                        out.append("  " * depth + f"{type(item).__name__}")
                        out.extend(walk(inner, depth + 1))
                    else:
                        out.append("  " * depth + "".join(
                            traceback.format_exception(type(item), item, item.__traceback__)))
                return out
            detail += "\n".join(walk(subs))
        (PKG / "tests" / "compliance_error.txt").write_text(detail, encoding="utf-8")
        check("session_completed", False, detail.replace("\n", " | ")[:600])

    passed = sum(1 for v in results.values() if isinstance(v, dict) and v["ok"])
    total = len([k for k in results if not k.startswith("_")])
    results["_summary"] = {"passed": passed, "total": total}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n==== MCP compliance: {passed}/{total} passed ====")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
