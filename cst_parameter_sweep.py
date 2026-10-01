from __future__ import annotations

import csv
import itertools
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from cst_automation import CSTSessionManager, _jsonable


def _parse_scalar(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return text
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer() and "." not in text and "e" not in text.lower():
        return int(number)
    return number


def parse_sweep_values(spec: Any) -> list[Any]:
    """Parse a sweep value spec such as [1, 2], "1,2,3", or "1:5:0.5"."""
    if isinstance(spec, dict):
        if "values" in spec:
            return parse_sweep_values(spec["values"])
        if {"start", "stop"} <= spec.keys() or {"min", "max"} <= spec.keys():
            start = spec.get("start", spec.get("min"))
            stop = spec.get("stop", spec.get("max"))
            step = spec.get("step", 1)
            return _range_values(float(start), float(stop), float(step))
        raise ValueError("sweep dict must contain values or start/stop[/step]")
    if isinstance(spec, (list, tuple)):
        return [_parse_scalar(item) for item in spec]
    if isinstance(spec, str):
        text = spec.strip()
        if "," in text:
            return [_parse_scalar(item) for item in text.split(",") if item.strip()]
        parts = [part.strip() for part in text.split(":")]
        if len(parts) in {2, 3} and all(parts):
            try:
                start = float(parts[0])
                stop = float(parts[1])
                step = float(parts[2]) if len(parts) == 3 else (1.0 if stop >= start else -1.0)
                return _range_values(start, stop, step)
            except ValueError:
                pass
        return [_parse_scalar(text)]
    return [_parse_scalar(spec)]


def _range_values(start: float, stop: float, step: float) -> list[Any]:
    if step == 0:
        raise ValueError("range step must not be zero")
    if start < stop and step < 0:
        raise ValueError("range step must be positive when start < stop")
    if start > stop and step > 0:
        raise ValueError("range step must be negative when start > stop")

    values: list[Any] = []
    current = start
    epsilon = abs(step) * 1e-9
    if step > 0:
        while current <= stop + epsilon:
            values.append(_normalize_number(current))
            current += step
    else:
        while current >= stop - epsilon:
            values.append(_normalize_number(current))
            current += step
    return values


def _normalize_number(value: float) -> int | float:
    rounded = round(value, 12)
    return int(rounded) if float(rounded).is_integer() else rounded


def build_sweep_cases(
    parameters: dict[str, Any],
    mode: str = "cartesian",
    max_cases: int = 200,
) -> list[dict[str, Any]]:
    if not parameters:
        raise ValueError("parameters must not be empty")
    if max_cases <= 0:
        raise ValueError("max_cases must be positive")

    parsed = {name: parse_sweep_values(spec) for name, spec in parameters.items()}
    for name, values in parsed.items():
        if not values:
            raise ValueError(f"parameter {name!r} has no values")

    normalized_mode = mode.lower().strip()
    names = list(parsed)
    cases: list[dict[str, Any]] = []
    if normalized_mode == "cartesian":
        for combo in itertools.product(*(parsed[name] for name in names)):
            cases.append(dict(zip(names, combo)))
    elif normalized_mode == "single":
        first = names[0]
        fixed = {name: parsed[name][0] for name in names[1:]}
        for value in parsed[first]:
            cases.append({first: value, **fixed})
    elif normalized_mode in {"zip", "paired"}:
        count = min(len(values) for values in parsed.values())
        cases = [{name: parsed[name][index] for name in names} for index in range(count)]
    else:
        raise ValueError("mode must be cartesian, single, or zip")

    if len(cases) > max_cases:
        raise ValueError(f"sweep would create {len(cases)} cases, above max_cases={max_cases}")
    return cases


def preview_sweep(parameters: dict[str, Any], mode: str = "cartesian", max_cases: int = 200) -> dict[str, Any]:
    cases = build_sweep_cases(parameters=parameters, mode=mode, max_cases=max_cases)
    return {
        "ok": True,
        "mode": mode,
        "case_count": len(cases),
        "parameters": {name: parse_sweep_values(spec) for name, spec in parameters.items()},
        "cases": cases,
    }


def _copy_project_bundle(source_project: Path, target_project: Path, overwrite: bool) -> None:
    source_project = source_project.expanduser().resolve()
    target_project = target_project.expanduser().resolve()
    if not source_project.is_file():
        raise FileNotFoundError(str(source_project))
    if target_project.exists() and not overwrite:
        raise FileExistsError(str(target_project))
    target_project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_project, target_project)

    source_dir = source_project.with_suffix("")
    target_dir = target_project.with_suffix("")
    if source_dir.is_dir():
        if target_dir.exists():
            if not overwrite:
                raise FileExistsError(str(target_dir))
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)


def _safe_name(value: str) -> str:
    allowed = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip("_") or "item"


def _case_vba(case: dict[str, Any]) -> str:
    """VBA that applies one parameter case.

    A bare history block: ``Sub Main``/``End Sub`` must NOT appear here. This body is
    handed to ``CSTSessionManager.execute_vba()``, which adds the ``Sub Main`` wrapper
    and routes it through ``_execute_vba_code`` (immediate execution). Sending it to
    ``add_to_history`` instead fails twice over, both verified live:

      * unwrapped, it is a history structure macro, and CST refuses the parameter
        change: "The rebuild operation cannot be used inside a structure macro." /
        "Prevented attempt to change the value for parameter X inside history rebuild"
        - and that failure can leave the Design Environment unresponsive;
      * wrapped in ``Sub Main`` it fails differently: "Unterminated block ... in
        add_to_history", because ``add_to_history`` expects a history block, not a macro.

    So: build a bare block here, let execute_vba() wrap and run it.
    """
    names = list(case)
    dim = len(names)
    lines = [f"Dim names(1 To {dim}) As String", f"Dim values(1 To {dim}) As String"]
    for index, name in enumerate(names, start=1):
        value = str(case[name]).replace('"', '""')
        lines.append(f'names({index}) = "{name}"')
        lines.append(f'values({index}) = "{value}"')
    lines.append("StoreParameters names, values")
    lines.append("Rebuild")
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_summary_csv(path: Path, rows: list[dict[str, Any]], parameter_names: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_index", "status", "case_project", *parameter_names, "touchstone_file", "error"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


class CSTParameterSweepRunner:
    def __init__(self, manager: CSTSessionManager) -> None:
        self.manager = manager

    def run_sweep(
        self,
        project_path: str,
        parameters: dict[str, Any],
        output_dir: str | None = None,
        mode: str = "cartesian",
        run_solver: bool = False,
        export_touchstone: bool = False,
        result_tree_paths: list[str] | None = None,
        max_cases: int = 200,
        overwrite: bool = False,
        continue_on_error: bool = True,
        close_after_case: bool = True,
        result_max_points: int = 2000,
    ) -> dict[str, Any]:
        source_project = Path(project_path).expanduser().resolve()
        cases = build_sweep_cases(parameters=parameters, mode=mode, max_cases=max_cases)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_output = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else source_project.parent / "sweeps" / f"{source_project.stem}_{timestamp}"
        )
        projects_dir = base_output / "cases"
        results_dir = base_output / "results"
        rows: list[dict[str, Any]] = []
        case_reports: list[dict[str, Any]] = []
        parameter_names = list(parameters)

        for index, case in enumerate(cases, start=1):
            case_id = f"case_{index:03d}"
            case_project = projects_dir / case_id / source_project.name
            row: dict[str, Any] = {
                "case_index": index,
                "status": "pending",
                "case_project": str(case_project),
                "touchstone_file": "",
                "error": "",
                **case,
            }
            report: dict[str, Any] = {"case_index": index, "case_id": case_id, "parameters": case}
            try:
                _copy_project_bundle(source_project, case_project, overwrite=overwrite)
                self.manager.open_project(str(case_project))
                # execute_vba(), NOT add_to_history(): a parameter change plus Rebuild
                # has to run through the immediate-execution channel. See _case_vba.
                self.manager.execute_vba(_case_vba(case))
                self.manager.save_project(str(case_project))
                if run_solver:
                    self.manager.run_solver()
                    self.manager.save_project(str(case_project))
                if export_touchstone:
                    touchstone = results_dir / case_id / f"{case_project.stem}.snp"
                    self.manager.export_touchstone(str(touchstone))
                    row["touchstone_file"] = str(touchstone)
                    report["touchstone_file"] = str(touchstone)
                if result_tree_paths:
                    exports = []
                    for tree_path in result_tree_paths:
                        result = self.manager.read_1d_result(
                            tree_path=tree_path,
                            cst_file=str(case_project),
                            max_points=result_max_points,
                        )
                        out = results_dir / case_id / f"{_safe_name(tree_path)}.json"
                        exports.append({"tree_path": tree_path, "file": _write_json(out, result)})
                    report["result_exports"] = exports
                row["status"] = "success"
                report["status"] = "success"
            except Exception as exc:
                row["status"] = "error"
                row["error"] = str(exc)
                report["status"] = "error"
                report["error_type"] = type(exc).__name__
                report["error"] = str(exc)
                if not continue_on_error:
                    rows.append(row)
                    case_reports.append(report)
                    break
            finally:
                if close_after_case:
                    self._close_active_project()
            rows.append(row)
            case_reports.append(report)

        summary_csv = _write_summary_csv(base_output / "sweep_summary.csv", rows, parameter_names)
        manifest = {
            "ok": all(row["status"] == "success" for row in rows),
            "source_project": str(source_project),
            "output_dir": str(base_output),
            "mode": mode,
            "case_count": len(cases),
            "completed_cases": sum(1 for row in rows if row["status"] == "success"),
            "failed_cases": sum(1 for row in rows if row["status"] == "error"),
            "run_solver": run_solver,
            "export_touchstone": export_touchstone,
            "summary_csv": summary_csv,
            "cases": case_reports,
        }
        manifest_path = _write_json(base_output / "sweep_manifest.json", manifest)
        manifest["manifest_path"] = manifest_path
        return manifest

    def _close_active_project(self) -> None:
        project = self.manager.project
        if project is None:
            return
        close = getattr(project, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        self.manager.project = None
