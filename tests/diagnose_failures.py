"""Focused diagnosis of the remaining failures, with the exact CST error text."""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Derived from this file and the running interpreter. It used to hard-code one
# machine's package folder, virtual-environment python and scratch folder.
PKG = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
WS = Path(tempfile.gettempdir()) / "cst_mcp_diag"
LOG = PKG / "tests" / "diag_progress.jsonl"
LOG.write_text("", encoding="utf-8")

PROBES = [
    ("library_material", "cst_load_material_from_library_tool",
     {"library_path": "Substrates\\FR-4 (lossy)", "material_name": "MCP_FR4"}),
    ("create_material_min", "cst_create_material_tool", {"name": "MCP_min"}),
    ("create_material_normal", "cst_create_material_tool",
     {"name": "MCP_norm", "material_type": "Normal", "epsilon": 4.3, "tan_d": 0.025}),
    ("create_material_lossy", "cst_create_material_tool",
     {"name": "MCP_cu", "material_type": "Lossy Metal", "sigma": 5.8e7}),
    ("assign_material", "cst_assign_material_tool",
     {"solid": "board:ground", "material": "PEC"}),
    ("frequency_overview", "cst_frequency_overview_tool", {}),
    ("list_monitors", "cst_list_monitors_tool", {}),
    ("export_ascii", "cst_export_ascii_tool",
     {"tree_path": "1D Results\\S-Parameters\\S1,1",
      "filename": str(WS / "evidence" / "s11_ascii.txt"), "mode": "RealImag"}),
    ("import_material_vba", "cst_add_to_history_tool",
     {"title": "load substrate material from library",
      "vba_code": 'With Material\n .Reset\n .Name "FR4_mcp"\n'
                  ' .Folder ""\n .Type "Normal"\n .Epsilon "4.3"\n .Mu "1.0"\n'
                  ' .Sigma "0.0"\n .TanD "0.025"\n .TanDFreq "2.45"\n'
                  ' .TanDGiven "True"\n .TanDModel "ConstTanD"\n .Rho "0.0"\n'
                  ' .ThermalType "Normal"\n .Colour "0.75", "0.95", "0.75"\n'
                  ' .Create\nEnd With'}),
]


def note(step, ok=None, **extra):
    rec = {"t": time.strftime("%H:%M:%S"), "step": step}
    if ok is not None:
        rec["ok"] = ok
    rec.update(extra)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(rec, ensure_ascii=False, default=str)[:1800], flush=True)


async def main() -> None:
    env = dict(os.environ)
    env["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
    env["CST_DESIGN_ENVIRONMENT_EXE"] = (
        r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe")
    env["CST_MCP_WORKSPACE"] = str(WS / "workspace")
    env["CST_MCP_EVIDENCE"] = str(WS / "evidence")
    params = StdioServerParameters(command=str(PY), args=[str(PKG / "mcp_server.py")],
                                   env=env, cwd=str(PKG))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool, args=None, timeout=180):
                try:
                    res = await session.call_tool(tool, args or {},
                                                  read_timeout_seconds=timedelta(seconds=timeout))
                except Exception as exc:  # noqa: BLE001
                    return True, f"EXC {type(exc).__name__}: {exc}"
                return bool(getattr(res, "isError", False)), "\n".join(
                    getattr(b, "text", "") or "" for b in res.content)

            err, text = await call("cst_connect_tool", {"launch_if_needed": True})
            note("connect", not err, body=text[:120])
            err, text = await call("cst_new_project_tool", {"project_type": "mws"})
            note("new_project", not err, body=text[:120])
            err, text = await call("cst_create_brick_tool",
                                   {"component": "board", "name": "ground",
                                    "xrange": [-10, 10], "yrange": [-10, 10],
                                    "zrange": [-1.6, 0], "material": "PEC"})
            note("brick_ground", not err, body=text[:200])

            for name, tool, args in PROBES:
                err, text = await call(tool, args)
                note(name, not err, body=text[:1400])

            # raw VBA probes for the query tools
            for label, vba in (
                ("raw_freq_range",
                 'Sub Main\nReportInformationToWindow "PROBE_A=" & Solver.GetFrequencyRange(0) & "|" & Solver.GetFrequencyRange(1)\nEnd Sub\n'),
                ("raw_getfmin",
                 'Sub Main\nDim a As String\na="?"\nOn Error Resume Next\na = CStr(Solver.GetFmin()) & "|" & CStr(Solver.GetFmax())\nOn Error GoTo 0\nReportInformationToWindow "PROBE_B=" & a\nEnd Sub\n'),
                ("raw_monitor_count",
                 'Sub Main\nDim n As Long, s As String\nDim nm As String\nn = Monitor.GetNumberOfMonitors()\ns = "count=" & n\nDim i As Long\nFor i = 1 To n\nnm = "?"\nOn Error Resume Next\nnm = Monitor.GetMonitorNameFromIndex(i)\nOn Error GoTo 0\ns = s & " [" & i & "]" & nm\nNext i\nReportInformationToWindow "PROBE_C=" & s\nEnd Sub\n'),
            ):
                err, text = await call("cst_run_vba_tool", {"vba_code": vba})
                note(label, not err, body=text[:800])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException as exc:  # noqa: BLE001
        note("ABORT", False, error=f"{type(exc).__name__}: {exc}")
