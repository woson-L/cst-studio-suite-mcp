"""Live verification of the consolidated CST-MCP against a real CST 2026.

Covers the full required chain: health -> project -> parameters -> geometry ->
materials -> port -> solver selection -> frequency range -> boundary/mesh ->
solve -> results -> verification -> evidence export.

Every step is written to a JSONL progress file, so a hang never loses the log.
Each call has its own timeout so one bad tool cannot stall the whole run.
"""
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

# Derived from this file and the running interpreter, so the runner works from any
# clone. It used to hard-code one machine's package folder, virtual-environment
# python and a scratch folder at the root of the C: drive.
PKG = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
WS = Path(tempfile.gettempdir()) / "cst_mcp_verify"
LOG = PKG / "tests" / "verify_progress.jsonl"
LOG.parent.mkdir(parents=True, exist_ok=True)
LOG.write_text("", encoding="utf-8")

RESULTS: dict[str, object] = {}


def note(step: str, ok: bool | None = None, **extra) -> None:
    rec = {"t": time.strftime("%H:%M:%S"), "step": step}
    if ok is not None:
        rec["ok"] = ok
    rec.update(extra)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    line = json.dumps(rec, ensure_ascii=False, default=str)
    print(line[:2000], flush=True)


def brief(text: str, n: int = 700) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n] + " ...<truncated>"


async def main() -> None:
    env = dict(os.environ)
    # Point at this machine's CST explicitly; on a real deployment .env does this.
    env["CST_INSTALL_ROOT"] = r"C:\Program Files\CST Studio Suite 2026"
    env["CST_DESIGN_ENVIRONMENT_EXE"] = (
        r"C:\Program Files\CST Studio Suite 2026\AMD64\CST DESIGN ENVIRONMENT_AMD64.exe"
    )
    env["CST_MCP_WORKSPACE"] = str(WS / "workspace")
    env["CST_MCP_EVIDENCE"] = str(WS / "evidence")

    params = StdioServerParameters(
        command=str(PY), args=[str(PKG / "mcp_server.py")], env=env, cwd=str(PKG)
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            note("tool_inventory", len(tools) >= 60, count=len(tools))
            RESULTS["tool_count"] = len(tools) >= 60

            async def call(tool: str, args: dict | None = None, timeout: int = 180):
                try:
                    res = await session.call_tool(tool, args or {},
                                                  read_timeout_seconds=timedelta(seconds=timeout))
                except Exception as exc:  # noqa: BLE001
                    return True, f"TIMEOUT/EXC {type(exc).__name__}: {exc}"
                return bool(getattr(res, "isError", False)), "\n".join(
                    getattr(b, "text", "") or "" for b in res.content
                )

            async def step(name: str, tool: str, args: dict | None = None, timeout: int = 180,
                           expect_error: bool = False) -> tuple[bool, str]:
                t0 = time.time()
                err, text = await call(tool, args, timeout)
                ok = (err == expect_error)
                RESULTS[name] = ok
                note(name, ok, tool=tool, elapsed=round(time.time() - t0, 2),
                     body=brief(text))
                return ok, text

            def check(name: str, ok: bool, detail: str = "") -> None:
                """Assert something about a previous step's output.

                The per-step result only says "the tool did not raise", which is not
                enough when the point of the step is the CONTENT it returned.
                """
                RESULTS[name] = bool(ok)
                note(name, bool(ok), body=brief(detail))

            # ---------------------------------------------------------- 1 health
            await step("health_check", "cst_health_check_tool", {})
            await step("detect", "cst_detect_tool", {})

            # ------------------------------------------------------- 2 project
            await step("connect", "cst_connect_tool", {"launch_if_needed": True})
            await step("new_project", "cst_new_project_tool", {"project_type": "mws"})
            # overwrite=True is required by design: CST refuses to save onto an
            # existing file and has no overwrite flag, so a repeatable test run must
            # opt in explicitly rather than relying on a stale file being absent.
            await step("save_project", "cst_save_project_tool",
                       {"path": str(WS / "workspace" / "verify_antenna.cst"),
                        "overwrite": True})

            # ---------------------------------------------------- 3 parameters
            await step("define_params", "cst_define_parameters_tool",
                       {"parameters": {"Lg": 60, "Wg": 50, "h": 1.6, "tcond": 0.035,
                                       "Lpatch": 26.91, "Wpatch": 37.584, "dinset": 21.6,
                                       "wfeed": 3.135}})
            await step("get_params", "cst_get_parameters_tool", {})
            await step("set_param", "cst_set_parameters_tool", {"parameters": {"Lpatch": 27.0}})
            await step("param_reject_list", "cst_set_parameters_tool",
                       {"parameters": {"Lpatch": [1, 2, 3]}}, expect_error=True)

            # ------------------------------------------------------ 4 geometry
            await step("units", "cst_add_to_history_tool",
                       {"title": "set units", "vba_code":
                        'With Units\n .SetUnit ("Length", "mm")\n .SetUnit ("Frequency", "GHz")\nEnd With'})
            # The library loader names the project material after the LIBRARY entry,
            # so material_name is applied as a rename. The brick below must therefore
            # use the requested name: referencing the library name here is what the
            # earlier version of this test did, and it silently masked the bug where
            # material_name was ignored. Assert the reported name is the real one.
            await step("load_library_material", "cst_load_material_from_library_tool",
                       {"library_path": "FR-4 (lossy)", "material_name": "FR4_substrate"})
            await step("brick_substrate", "cst_create_brick_tool",
                       {"component": "board", "name": "substrate",
                        "xrange": ["-Lg/2", "Lg/2"], "yrange": ["-Wg/2", "Wg/2"],
                        "zrange": ["-h", "0"], "material": "FR4_substrate"})
            await step("brick_ground", "cst_create_brick_tool",
                       {"component": "board", "name": "ground",
                        "xrange": ["-Lg/2", "Lg/2"], "yrange": ["-Wg/2", "Wg/2"],
                        "zrange": ["-h-tcond", "-h"], "material": "PEC"})
            await step("brick_patch", "cst_create_brick_tool",
                       {"component": "antenna", "name": "patch",
                        "xrange": ["-Lpatch/2", "Lpatch/2"], "yrange": ["-Wpatch/2", "Wpatch/2"],
                        "zrange": ["0", "tcond"], "material": "PEC"})
            await step("brick_slot", "cst_create_brick_tool",
                       {"component": "antenna", "name": "slot",
                        "xrange": ["-Lpatch/2", "-Lpatch/2+dinset"],
                        "yrange": ["wfeed/2", "wfeed/2+2"], "zrange": ["-0.1", "tcond+0.1"],
                        "material": "PEC"})
            await step("boolean_subtract", "cst_boolean_tool",
                       {"operation": "subtract", "target": "antenna:patch", "tool": "antenna:slot"})
            await step("brick_feed", "cst_create_brick_tool",
                       {"component": "antenna", "name": "feed",
                        "xrange": ["-Lg/2", "0"], "yrange": ["-wfeed/2", "wfeed/2"],
                        "zrange": ["0", "tcond"], "material": "PEC"})
            await step("torus_reject_zero", "cst_create_cone_tool",
                       {"component": "antenna", "name": "badcone", "axis": "z",
                        "bottom_radius": 0, "top_radius": 0, "ranges": [0, 1]},
                       expect_error=True)

            # ----------------------------------------------------- 5 materials
            # Proof that material_name really renamed the library material: the brick
            # above was built with "FR4_substrate", and this audit reports the material
            # CST actually attached to that solid.
            _, audit_text = await step("material_rename_check", "cst_model_audit_tool", {})
            check(
                "library material was renamed to the requested name",
                "FR4_substrate" in audit_text,
                detail=audit_text[:400],
            )
            await step("create_material", "cst_create_material_tool",
                       {"name": "MCP_FR4", "material_type": "Normal", "epsilon": 4.3,
                        "tan_d": 0.025, "tan_d_freq": 2.45})
            await step("assign_material", "cst_assign_material_tool",
                       {"solid": "board:substrate", "material": "MCP_FR4"})

            # --------------------------------------------------------- 6 ports
            await step("discrete_port", "cst_add_discrete_port_tool",
                       {"port_number": 1, "point1": ["-Lg/2", 0, "-h"],
                        "point2": ["-Lg/2", 0, "tcond"], "impedance": 50.0})
            await step("list_ports", "cst_list_ports_tool", {})

            # ------------------------------------------ 7 solver + frequency
            await step("set_solver", "cst_set_solver_tool", {"solver": "HF Frequency Domain"})
            await step("get_solver", "cst_get_solver_tool", {})
            await step("set_frequency", "cst_set_frequency_range_tool",
                       {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"})
            await step("configure_fd", "cst_configure_fd_solver_tool",
                       {"mesh": "Tetrahedral", "sweep": "General Purpose", "order": "Second",
                        "accuracy": "1e-4", "mesh_adaption": False})
            await step("frequency_overview", "cst_frequency_overview_tool", {})
            await step("solver_reject_bad", "cst_set_solver_tool",
                       {"solver": "not-a-solver"}, expect_error=True)
            await step("configure_td_reject_bad_acc", "cst_configure_td_solver_tool",
                       {"accuracy": "-200"}, expect_error=True)
            await step("configure_td_ok", "cst_configure_td_solver_tool",
                       {"accuracy": "-30", "mesh_type": "Tetrahedral"})
            await step("back_to_fd", "cst_set_solver_tool", {"solver": "HF Frequency Domain"})
            await step("refrequency", "cst_set_frequency_range_tool",
                       {"fmin": 2.2, "fmax": 2.7, "unit": "GHz"})
            await step("reconfig_fd", "cst_configure_fd_solver_tool",
                       {"mesh": "Tetrahedral", "sweep": "General Purpose", "order": "Second",
                        "accuracy": "1e-4", "mesh_adaption": False})

            # ------------------------------------------------- 8 domain + mesh
            await step("boundary_reject_bad", "cst_set_boundary_tool",
                       {"all": "banana"}, expect_error=True)
            await step("set_boundary", "cst_set_boundary_tool", {"all": "expanded open"})
            await step("set_background", "cst_set_background_tool",
                       {"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": True})
            await step("set_mesh", "cst_set_mesh_tool",
                       {"mesh_type": "Tetrahedral", "steps_per_wavelength": 12})
            await step("add_monitor", "cst_add_monitor_tool",
                       {"name": "farfield_2400", "field_type": "Farfield", "frequency": 2.4})
            await step("monitor_reject_bad", "cst_add_monitor_tool",
                       {"name": "bad", "field_type": "nonsense"}, expect_error=True)
            await step("list_monitors", "cst_list_monitors_tool", {})

            # --------------------------------------------------------- 9 solve
            # This is the save -> solve -> save loop that previously could never target
            # the same path twice. It now succeeds because the target is the active
            # project file, which the tool saves in place without deleting anything.
            await step("save_before_solve", "cst_save_project_tool",
                       {"path": str(WS / "workspace" / "verify_antenna.cst"),
                        "overwrite": True})
            await step("run_solver", "cst_run_solver_tool", {}, timeout=900)
            await step("messages", "cst_messages_tool", {"limit": 15})

            # ------------------------------------------------------ 10 results
            await step("list_results", "cst_list_results_tool", {})
            await step("read_s11", "cst_read_s11_tool", {"target_frequency": 2.4})
            await step("read_zref", "cst_read_reference_impedance_tool", {})
            await step("read_port_info", "cst_read_port_info_tool", {})
            # Regression guard for the fixed verdict threshold: this project uses a
            # discrete port, so there is no port-mode cutoff and the verdict must stay
            # the discrete-port message - never "OK"/"WARNING" derived from a hardcoded
            # frequency. `operating_frequency` must be accepted and echoed back.
            await step("port_info_with_operating_freq", "cst_read_port_info_tool",
                       {"operating_frequency": 2.4})
            await step("port_info_reject_bad_arg", "cst_read_port_info_tool",
                       {"operating_frequency": "not-a-number"}, expect_error=True)
            await step("energy_summary", "cst_energy_summary_tool", {"frequency": 2.4})
            await step("model_audit", "cst_model_audit_tool", {})

            # ----------------------------------------------------- 11 evidence
            await step("export_touchstone", "cst_export_touchstone_tool",
                       {"filename": str(WS / "evidence" / "verify_s11"), "impedance": 50.0,
                        "data_format": "RI"})
            await step("export_ascii", "cst_export_ascii_tool",
                       {"tree_path": "1D Results\\S-Parameters\\S1,1",
                        "filename": str(WS / "evidence" / "verify_s11.txt"),
                        "mode": "RealImag"})
            await step("summary_json", "cst_write_summary_json_tool",
                       {"out_path": str(WS / "evidence" / "result_summary.json"),
                        "target_frequency": 2.4})

            # --------------------------------------------------------- 12 meta
            await step("list_mcp_tools", "cst_list_mcp_tools_tool", {})
            await step("manifest", "cst_tool_manifest_tool",
                       {"out_path": str(PKG / "docs" / "mcp_tools.json")})
            await step("health_guard", "cst_add_to_history_tool",
                       {"title": "must be refused",
                        "vba_code": 'StoreParameters n, v\nRebuild'}, expect_error=True)

            # ------------------------------------- 13 extra geometry on a scratch project
            # Kept off the solved model: decorative solids distort the mesh ratio
            # and can make the frequency domain preconditioner run out of memory.
            await step("geom_project", "cst_new_project_tool", {"project_type": "mws"})
            await step("cylinder", "cst_create_cylinder_tool",
                       {"component": "parts", "name": "via", "axis": "z", "radius": 1.0,
                        "ranges": [0, 5], "material": "PEC"})
            await step("sphere", "cst_create_sphere_tool",
                       {"component": "parts", "name": "ball", "center": [0, 0, 12],
                        "radius": 4.0, "material": "PEC"})
            await step("torus", "cst_create_torus_tool",
                       {"component": "parts", "name": "ring", "center": [20, 0, 0],
                        "ring_radius": 6.0, "tube_radius": 1.5, "material": "PEC"})
            await step("cone", "cst_create_cone_tool",
                       {"component": "parts", "name": "horn", "axis": "z",
                        "bottom_radius": 2.0, "top_radius": 5.0, "ranges": [0, 8],
                        "material": "PEC"})
            await step("bondwire", "cst_create_bondwire_tool",
                       {"name": "bw1", "point1": [-10, 0, 0],
                        "point2": [-2, 0, 1], "height": 2.0, "radius": 0.2,
                        "material": "PEC"})
            await step("component", "cst_new_component_tool", {"name": "spare"})
            await step("move_solid", "cst_move_solid_to_component_tool",
                       {"solid": "parts:ring", "component": "spare"})
            await step("transform_translate", "cst_transform_tool",
                       {"operation": "translate", "name": "parts:via", "vector": [0, 10, 0]})
            await step("transform_rotate", "cst_transform_tool",
                       {"operation": "rotate", "name": "parts:via",
                        "center": [0, 0, 0], "axis": "z", "angle": 45})
            await step("transform_scale", "cst_transform_tool",
                       {"operation": "scale", "name": "parts:ball",
                        "center": [0, 0, 12], "scale": [2, 2, 2]})
            await step("transform_mirror", "cst_transform_tool",
                       {"operation": "mirror", "name": "parts:horn",
                        "center": [0, 0, 0], "plane": "yz"})
            await step("transform_missing_shape", "cst_transform_tool",
                       {"operation": "translate", "name": "parts:nope",
                        "vector": [1, 0, 0]}, expect_error=True)
            await step("rename_solid", "cst_rename_solid_tool",
                       {"old_name": "parts:via", "new_name": "post"})
            await step("delete_solid", "cst_delete_solid_tool", {"name": "parts:post"})
            await step("geom_audit", "cst_model_audit_tool", {})

            # ------------------------------------- 14 solver configuration coverage
            await step("eigenmode_solver", "cst_set_solver_tool", {"solver": "HF Eigenmode"})
            await step("eigenmode_config", "cst_configure_eigenmode_solver_tool",
                       {"n_modes": 3, "mesh_type": "Tetrahedral Mesh", "method": "Automatic"})
            await step("eigenmode_reject_jdm", "cst_configure_eigenmode_solver_tool",
                       {"n_modes": 1, "method": "JDM"}, expect_error=True)
            await step("td_solver", "cst_set_solver_tool", {"solver": "HF Time Domain"})
            await step("td_config", "cst_configure_td_solver_tool",
                       {"accuracy": "-30"}
                       )
            await step("close_geom_project", "cst_close_project_tool", {})

    passed = sum(1 for v in RESULTS.values() if v is True)
    note("SUMMARY", True, passed=passed, total=len(RESULTS),
         failed=[k for k, v in RESULTS.items() if v is not True])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException as exc:  # noqa: BLE001
        note("HARNESS_ABORT", False, error=f"{type(exc).__name__}: {exc}")
        passed = sum(1 for v in RESULTS.values() if v is True)
        print(f"\n==== aborted: {passed}/{len(RESULTS)} checks passed before the abort ====")
        print("failed:", [k for k, v in RESULTS.items() if v is not True])
        raise SystemExit(1)
    passed = sum(1 for v in RESULTS.values() if v is True)
    print(f"\n==== {passed}/{len(RESULTS)} checks passed ====")
    print("failed:", [k for k, v in RESULTS.items() if v is not True])
