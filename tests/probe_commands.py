"""Probe the replacement VBA commands and print what CST reports."""
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

PROBES = {
    "freq_A": 'Sub Main\nReportInformationToWindow "R1=" & CStr(Solver.GetFmin()) & "|" & CStr(Solver.GetFmax())\nEnd Sub\n',
    "freq_B": 'Sub Main\nReportInformationToWindow "R2=" & CStr(Solver.FrequencyRange) & "\nEnd Sub\n',
    "mon_A": 'Sub Main\nDim n As Long\nn = Monitor.GetNumberOfMonitors()\nReportInformationToWindow "R3=count:" & n\nEnd Sub\n',
    "mon_B": 'Sub Main\nDim n As Long, i As Long, s As String\nn = Monitor.GetNumberOfMonitors()\nFor i = 1 To n\ns = s & Monitor.GetMonitorNameFromIndex(i) & ";"\nNext i\nReportInformationToWindow "R4=" & s\nEnd Sub\n',
    "mat_lib": 'Sub Main\nWith MaterialLibrary\n .LoadMaterialFromLibrary ("FR-4 (lossy)", "", True)\nEnd With\nReportInformationToWindow "R5=library-ok"\nEnd Sub\n',
    "mat_colour": 'Sub Main\nWith Material\n .Reset\n .Name "MCP_colour"\n .FrqType "hf"\n .Type "Normal"\n .Epsilon "4.3"\n .Mu "1.0"\n .Colour "0.75","0.95","0.75"\n .Create\nEnd With\nReportInformationToWindow "R6=colour-ok"\nEnd Sub\n',
    "mat_getters": 'Sub Main\nDim m As Long\nm = Material.GetNumberOfMaterials()\nReportInformationToWindow "R7=materials:" & m & " type:" & Material.GetTypeOfMaterial("MCP_colour") & " eps:" & Material.GetEpsilon("MCP_colour")\nEnd Sub\n',
}


async def main() -> None:
    env = dict(os.environ)
    env["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
    env["CST_DESIGN_ENVIRONMENT_EXE"] = (
        r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe")
    env["CST_MCP_WORKSPACE"] = str(WS / "workspace")
    env["CST_MCP_EVIDENCE"] = str(WS / "evidence")
    out = {}
    params = StdioServerParameters(command=str(PY), args=[str(PKG / "mcp_server.py")],
                                   env=env, cwd=str(PKG))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool, args=None, timeout=120):
                try:
                    res = await session.call_tool(tool, args or {},
                                                  read_timeout_seconds=timedelta(seconds=timeout))
                except Exception as exc:  # noqa: BLE001
                    return True, f"EXC {type(exc).__name__}: {exc}"
                return bool(getattr(res, "isError", False)), "\n".join(
                    getattr(b, "text", "") or "" for b in res.content)

            err, text = await call("cst_connect_tool", {"launch_if_needed": True})
            print("connect", err)
            err, text = await call("cst_new_project_tool", {"project_type": "mws"})
            print("new_project", err)
            await call("cst_set_frequency_range_tool", {"fmin": 2.2, "fmax": 2.7})
            await call("cst_add_monitor_tool", {"name": "ff1", "field_type": "Farfield",
                                                "frequency": 2.4})

            for label, vba in PROBES.items():
                err, text = await call("cst_run_vba_tool", {"vba_code": vba})
                time.sleep(0.3)
                err2, msgs = await call("cst_messages_tool", {"limit": 30})
                found = []
                try:
                    parsed = json.loads(msgs)
                    for m in parsed.get("messages", []):
                        t = m.get("text", "")
                        if any(t.startswith(k) for k in ("R1=", "R2=", "R3=", "R4=",
                                                         "R5=", "R6=", "R7=")):
                            found.append(t)
                    errm = [m["text"][:160] for m in parsed.get("messages", [])
                            if m.get("type") == "ERROR"]
                except Exception:  # noqa: BLE001
                    errm = [msgs[:200]]
                out[label] = {"is_error": err, "found": found[-1:], "errors": errm[-2:]}
                print(f"--- {label}: err={err}")
                for f in found[-1:]:
                    print("    ", f)
                for e in errm[-2:]:
                    print("    ERR", e.replace("\n", " "))

    (PKG / "tests" / "probe_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
