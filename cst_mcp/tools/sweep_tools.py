"""Parameter-sweep tools: enumerate cases, then run them.

Two tools, deliberately split so the expensive half is never entered blind:

* ``cst_sweep_preview_tool`` computes the case list and **never touches CST** — it
  does not even import the CST session. Always call it first: it is what turns
  "sweep L and w" into a concrete case count you can approve.
* ``cst_sweep_run_tool`` executes the cases: one copied project per case, parameters
  applied, optionally solved, optionally exported.

Implementation notes
--------------------
The enumerating and file-laying logic lives in the top-level module
``cst_parameter_sweep`` (pure Python, no CST dependency); the CST session it drives
lives in ``cst_automation``. Both are kept out of ``cst_mcp`` on purpose so this
family stays replaceable/extendable without touching the core package.

Two details matter for correctness:

1. ``cst_automation`` resolves the CST install from ``os.environ["CST_INSTALL_ROOT"]``
   and does not import ``cst_mcp.config``. Loading ``.env`` is therefore forced here,
   before the manager is built, so a client that starts the server from a different
   working directory still finds CST.
2. The per-case parameter block is wrapped in ``Sub Main`` (see ``_case_vba`` in
   ``cst_parameter_sweep``). Unwrapped it is a history structure macro, which CST
   refuses and which can leave the Design Environment unresponsive.

This family is the worked example for "how to add a tool family by hand" — see
``docs/extend/add-a-tool-family.md``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import config
from ..registry import ToolRegistry

CATEGORY = "sweep"


def register_tools(registry: ToolRegistry) -> None:
    def _preview():
        # Imported inside the call so that a machine without these modules can still
        # run every other tool: this family is optional, not core.
        from cst_parameter_sweep import preview_sweep

        return preview_sweep

    def _manager():
        """Build a connected CST session manager for the sweep runner.

        Two things the bare ``CSTSessionManager`` does not do for itself:

        1. ``cst_automation`` reads ``CST_INSTALL_ROOT`` from the environment and does
           not import ``cst_mcp.config``, so `.env` is forced in here first.
        2. ``CSTSessionManager.connect()`` only ever attaches to an ALREADY RUNNING
           Design Environment - with none running it raises
           ``RuntimeError: No DEs found to connect to.``, which is what every case
           failed with on the first live sweep test. Try to attach, and launch only
           if that fails, so an existing CST with open projects is reused rather than
           duplicated.
        """
        config.load_env()
        from cst_automation import CSTSessionManager

        manager = CSTSessionManager()
        try:
            manager.connect(launch_if_needed=False)
        except Exception:  # noqa: BLE001 - nothing running yet, so start one
            manager.connect(launch_if_needed=True)
        return manager

    @registry.tool(
        "cst_sweep_preview_tool",
        "Expand a parameter sweep spec into concrete cases and report the case count. Does not start CST.",
        CATEGORY,
        params={"parameters": "dict", "mode": "str", "max_cases": "int"},
        required=["parameters"],
        returns="{ok, mode, case_count, parameters, cases}",
        examples=[{"parameters": {"L": "48:52:2"}, "mode": "single"},
                  {"parameters": {"L": [48, 50], "w": [2, 3]}, "mode": "cartesian",
                   "max_cases": 20}],
        notes=[
            "Call this BEFORE cst_sweep_run_tool: it is the cheap half and it never",
            "opens CST or writes files. Show the case count to the user first when the",
            "count is large or the cases will be solved.",
            "Value specs accept a list [48, 50] or a range string 'start:stop:step'.",
            "mode: single (vary the first parameter only), zip (pair values, shortest",
            "wins), cartesian (full product - the only mode whose count multiplies).",
            "max_cases is a guard, not a target: exceeding it raises instead of running.",
        ],
        replaces_vba="(no CST VBA - pure case enumeration)",
    )
    def sweep_preview(parameters: dict, mode: str = "cartesian",
                      max_cases: int = 200) -> dict[str, Any]:
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters must be a non-empty object, e.g. {\"L\": \"48:52:2\"}")
        return _preview()(parameters=parameters, mode=mode, max_cases=max_cases)

    @registry.tool(
        "cst_sweep_run_tool",
        "Run a parameter sweep: one copied project per case, parameters applied, optional solve and export.",
        CATEGORY,
        params={"project_path": "str", "parameters": "dict", "output_dir": "str | null",
                "mode": "str", "run_solver": "bool", "export_touchstone": "bool",
                "result_tree_paths": "list | null", "max_cases": "int",
                "overwrite": "bool", "continue_on_error": "bool",
                "close_after_case": "bool", "result_max_points": "int"},
        required=["project_path", "parameters"],
        returns="{ok, mode, case_count, completed, failed, output_dir, summary_csv, manifest}",
        examples=[{"project_path": "C:\\\\Users\\\\<user>\\\\Desktop\\\\123.cst",
                   "parameters": {"L": "48:52:2"}, "mode": "single",
                   "run_solver": False}],
        notes=[
            "Does not modify the source project: each case gets its own copy.",
            "run_solver defaults to False - the sweep is cheap and safe by default, and",
            "a 100-case sweep with solves can take hours. Set it only when you mean it.",
            "Output defaults to <source folder>/sweeps/<project>_<timestamp>/ and does",
            "not depend on CST_MCP_WORKSPACE, so it works even if .env is incomplete.",
            "Reads sweep_summary.csv for the per-case table and sweep_manifest.json for",
            "the full record. Report failures from those files, not from memory.",
            "Always preview first with cst_sweep_preview_tool.",
        ],
        replaces_vba="(no single CST command - orchestrates per-case parameter changes)",
    )
    def sweep_run(project_path: str, parameters: dict, output_dir: str | None = None,
                  mode: str = "cartesian", run_solver: bool = False,
                  export_touchstone: bool = False,
                  result_tree_paths: list | None = None, max_cases: int = 200,
                  overwrite: bool = False, continue_on_error: bool = True,
                  close_after_case: bool = True,
                  result_max_points: int = 2000) -> dict[str, Any]:
        source = Path(project_path).expanduser()
        if not source.is_file():
            raise ValueError(f"project not found: {source}")
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters must be a non-empty object")
        from cst_parameter_sweep import CSTParameterSweepRunner

        runner = CSTParameterSweepRunner(_manager())
        return runner.run_sweep(
            project_path=str(source),
            parameters=parameters,
            output_dir=output_dir,
            mode=mode,
            run_solver=run_solver,
            export_touchstone=export_touchstone,
            result_tree_paths=list(result_tree_paths) if result_tree_paths else None,
            max_cases=max_cases,
            overwrite=overwrite,
            continue_on_error=continue_on_error,
            close_after_case=close_after_case,
            result_max_points=result_max_points,
        )
