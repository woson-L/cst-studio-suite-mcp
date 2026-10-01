"""Result reading, verification and evidence export.

The verification tools exist because a successful solve is not proof of a correct
result. The specific trap this guards against, seen in practice on a microstrip
patch antenna:

* a waveguide port was used on a 1.6 mm microstrip cross-section;
* the solver completed and the result tree contained `S1,1`;
* but the port mode cutoff frequency was 51.9 GHz and the mode wave impedance was
  6.2 kohm, i.e. the mode was evanescent at 2.4 GHz, and the S-parameters were
  referenced to 7623 ohm instead of 50 ohm;
* S11 looked like a flat -0.6 dB line, which is easy to mistake for an antenna.

`cst_read_reference_impedance_tool` and `cst_read_port_info_tool` report exactly
the two numbers that expose this.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .. import config
from ..registry import ToolRegistry
from ..session import session

CATEGORY = "results"
CATEGORY_EXPORT = "export"
CATEGORY_VERIFY = "verify"

#: Module-level alias for the session factory, kept deliberately short and
#: un-shadowed. Tests replace this single name to exercise the result-reading
#: logic without a CST process. Note the registered tools bind the same object
#: as a local named `s` inside `register_tools`, and the two module-level helpers
#: below bind a local `s` to the *session instance* - so this alias must not be
#: called `s`, or those locals shadow it and the patch silently misses.
_sess = session

S11_PATHS = (
    "1D Results\\S-Parameters\\S1,1",
    "1D Results\\S-Parameters\\S1,1 (0.5)",
)


def _nearest(data: list, target: float) -> tuple[float, Any] | None:
    best = None
    for row in data:
        # Share one parser with read_s11: a bare float() here silently skipped the
        # parenthesised complex form ("(2.4+0j)") that CST returns for 1D results,
        # so every row was discarded and the caller saw "no nearest sample".
        freq = _to_float(row[0]) if row else None
        if freq is None:
            continue
        if best is None or abs(freq - target) < abs(best[0] - target):
            best = (freq, row[1] if len(row) > 1 else None)
    return best


def _to_float(value: Any) -> float | None:
    """Parse a CST scalar. Handles plain numbers and the "(a+bj)" complex repr.

    CST hands complex 1D results back as the Python repr of a complex, e.g.
    "(-0.1+0.2j)" for S1,1 or "(50+0j)" for a port reference impedance. The real
    part is the wanted value. Let the interpreter do the parsing: the previous
    hand-rolled split cut `text[1:]`, which ate the sign for a negative real part
    and - worse - ate the leading DIGIT otherwise, turning "(50+0j)" into 0.0 and
    "(51.9e9+0j)" into 1.9e9. A corrupted cutoff frequency then made
    cst_read_port_info_tool declare an evanescent port healthy.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, complex):
        return float(value.real)
    text = str(value).strip()
    if text.startswith("(") and text.endswith(")"):
        try:
            return float(complex(text).real)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _solver_band() -> tuple[float, float] | None:
    """Return the solver's (fmin, fmax) in the project's unit, or None.

    Verified on CST 2026.2: `Solver.GetFmin()` / `Solver.GetFmax()` work, whereas
    `Solver.GetFrequencyRange(index)` and `CStr(Solver.FrequencyRange)` do not.
    The values are reported back through the message window because the VBA
    bridge has no return channel.
    """
    marker = "MCPPORTBAND="
    try:
        _sess().run_vba(
            "Sub Main\n"
            "Dim b As String\n"
            "b = \"?\"\n"
            "On Error Resume Next\n"
            "b = CStr(Solver.GetFmin()) & \"|\" & CStr(Solver.GetFmax())\n"
            "On Error GoTo 0\n"
            f'ReportInformationToWindow "{marker}" & b\n'
            "End Sub\n"
        )
        for message in reversed(_sess().messages(limit=15)):
            if marker in message["text"]:
                payload = message["text"].split(marker, 1)[1].strip()
                low, _, high = payload.partition("|")
                fmin, fmax = _to_float(low), _to_float(high)
                if fmin is not None and fmax is not None:
                    return (fmin, fmax)
                return None
    except Exception:  # noqa: BLE001 - the verdict degrades to UNKNOWN, never crashes
        return None
    return None


# ------------------------------------------------------------------ shared impls
def model_audit() -> dict[str, Any]:
    """Audit the built model: solids, materials, volumes and bounding boxes.

    Module-level so other tool families (the runtime bridge) can reuse it.
    """
    s = _sess()
    marker = "MCPAUDIT="
    s.run_vba(
        "Sub Main\n"
        "Dim n As Long, i As Long, nm As String\n"
        'Dim x1 As Double, x2 As Double, y1 As Double, y2 As Double, z1 As Double, z2 As Double\n'
        "Dim ok As Boolean, s As String\n"
        "On Error Resume Next\n"
        "n = Solid.GetNumberOfShapes()\n"
        "For i = 0 To n - 1\n"
        "nm = Solid.GetNameOfShapeFromIndex(i)\n"
        "ok = False\n"
        "ok = Solid.GetLooseBoundingBoxOfShape(nm, x1, x2, y1, y2, z1, z2)\n"
        's = s & nm & "|" & Solid.GetMaterialNameForShape(nm) & "|" & Solid.GetVolume(nm)\n'
        "If ok Then\n"
        's = s & "|" & x1 & "," & x2 & "," & y1 & "," & y2 & "," & z1 & "," & z2\n'
        "End If\n"
        "s = s & vbLf\n"
        "Next i\n"
        f'ReportInformationToWindow "{marker}" & s\n'
        "End Sub\n"
    )
    for m in reversed(s.messages(limit=20)):
        if marker in m["text"]:
            body = m["text"].split(marker, 1)[1]
            shapes = []
            for line in body.replace("\r", "\n").split("\n"):
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = line.split("|")
                entry: dict[str, Any] = {"name": parts[0],
                                         "material": parts[1] if len(parts) > 1 else None,
                                         "volume": _to_float(parts[2]) if len(parts) > 2 else None}
                if len(parts) > 3:
                    coords = [_to_float(x) for x in parts[3].split(",")]
                    if len(coords) == 6:
                        entry["bbox"] = {"x": coords[0:2], "y": coords[2:4], "z": coords[4:6]}
                shapes.append(entry)
            return {"ok": True, "shape_count": len(shapes), "shapes": shapes}
    return {"ok": False, "error": "CST did not return the shape list",
            "messages": s.messages(limit=10)}


def export_touchstone(filename: str, impedance: float = 50.0, export_type: str = "S",
                      data_format: str = "RI", frequency_range: str = "Full") -> dict[str, Any]:
    """Export S-parameters as Touchstone. Module-level so the runtime bridge can reuse it."""
    s = _sess()
    target = config.resolve_path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "With TOUCHSTONE", " .Reset", f' .FileName ("{target}")',
        f' .Impedance ("{impedance}")', f' .ExportType ("{export_type}")',
        f' .Format ("{data_format}")', f' .FrequencyRange ("{frequency_range}")',
        ' .Renormalize ("True")', ' .UseARResults ("False")', ' .SetNSamples ("0")',
        " .Write", "End With",
    ]
    s.run_vba("\n".join(lines))
    found = sorted(target.parent.glob(target.name + ".s*p"))
    return {"ok": True, "filename": str(target), "written": [str(p) for p in found]}


def register_tools(registry: ToolRegistry) -> None:
    # Late-bound on purpose: call `_sess` at call time rather than capturing the
    # factory now, so replacing the module-level `_sess` (tests, or a swapped
    # session backend) is seen by every registered tool.
    s = lambda *a, **k: _sess(*a, **k)  # noqa: E731

    @registry.tool(
        "cst_list_results_tool", "List the items of the 3D or schematic result tree.",
        CATEGORY, params={"cst_file": "str | null", "module": "str"},
        examples=[{"module": "3d"}],
        returns="{count, items}",
        replaces_vba="Result tree enumeration",
    )
    def list_results(cst_file: str | None = None, module: str = "3d") -> dict[str, Any]:
        return s().list_results(cst_file=cst_file, module=module)

    @registry.tool(
        "cst_read_result_tool", "Read a 1D result tree item (S-parameters, efficiency, power, convergence).",
        CATEGORY,
        params={"tree_path": "str", "cst_file": "str | null", "module": "str",
                "max_points": "int", "at_frequency": "float | null"},
        required=["tree_path"],
        examples=[{"tree_path": "1D Results\\S-Parameters\\S1,1"},
                  {"tree_path": "1D Results\\S-Parameters\\S1,1", "at_frequency": 2.4}],
        returns="{tree_path, length, data, at_frequency?}",
        notes=[
            "S-parameters come back as complex values: convert with 20*log10(abs(S)) yourself.",
            "Use at_frequency to get the nearest sample to a frequency of interest.",
        ],
        replaces_vba="ResultTree / SelectTreeItem + Result1D getters",
    )
    def read_result(tree_path: str, cst_file: str | None = None, module: str = "3d",
                    max_points: int = 4000, at_frequency: float | None = None) -> dict[str, Any]:
        out = s().read_result(tree_path, cst_file=cst_file, module=module, max_points=max_points)
        if at_frequency is not None and out.get("data"):
            hit = _nearest(out["data"], float(at_frequency))
            if hit:
                out["at_frequency"] = {"requested": float(at_frequency),
                                       "sample": hit[0], "value": hit[1]}
        return out

    @registry.tool(
        "cst_read_s11_tool",
        "Read S11 and report it in dB at a target frequency (the usual acceptance check).",
        CATEGORY_VERIFY,
        params={"tree_path": "str", "target_frequency": "float", "cst_file": "str | null"},
        examples=[{"target_frequency": 2.4}],
        returns="{s11_db_at_target, best_s11_db, best_frequency, meets_minus10dB}",
        notes=["dB is computed here as 20*log10(abs(S11)) so it cannot be misread."],
    )
    def read_s11(tree_path: str = S11_PATHS[0], target_frequency: float = 2.4,
                 cst_file: str | None = None) -> dict[str, Any]:
        out = s().read_result(tree_path, cst_file=cst_file, max_points=20000)
        data = out.get("data") or []
        if not data:
            return {"ok": False, "error": f"no data at {tree_path}. Solve first, then list results."}
        rows = []
        for row in data:
            freq = _to_float(row[0]) if len(row) > 0 else None
            mag = None
            if len(row) > 1:
                raw = row[1]
                text = str(raw)
                if text.startswith("(") and text.endswith(")"):
                    body = text.strip("()")
                    try:
                        complex_value = complex(body)
                        mag = abs(complex_value)
                    except ValueError:
                        mag = None
                if mag is None:
                    value = _to_float(raw)
                    mag = abs(value) if value is not None else None
            if freq is not None and mag not in (None, 0.0):
                rows.append((freq, 20 * math.log10(mag)))
        if not rows:
            return {"ok": False, "error": "could not interpret the S11 data"}
        hit = min(rows, key=lambda r: abs(r[0] - float(target_frequency)))
        best = min(rows, key=lambda r: r[1])
        return {
            "ok": True,
            "tree_path": tree_path,
            "target_frequency": float(target_frequency),
            "s11_db_at_target": round(hit[1], 3),
            "sample_frequency": hit[0],
            "best_s11_db": round(best[1], 3),
            "best_frequency": best[0],
            "meets_minus10dB": bool(hit[1] < -10.0),
            "n_points": len(rows),
        }

    @registry.tool(
        "cst_read_reference_impedance_tool",
        "Read the S-parameter reference impedance (ZRef) - must match the impedance you intend.",
        CATEGORY_VERIFY, params={"cst_file": "str | null"},
        returns="{value_at_first, value_at_last, sample}",
        notes=[
            "A discrete port with Impedance=50 should give exactly 50+0j.",
            "If this is not your intended impedance, every S-parameter is wrong.",
        ],
    )
    def read_zref(cst_file: str | None = None) -> dict[str, Any]:
        out = s().read_result("1D Results\\Reference Impedance\\ZRef 1(1)",
                              cst_file=cst_file, max_points=5)
        data = out.get("data") or []
        if not data:
            return {"ok": False, "error": "ZRef not found; has the project been solved?"}
        first = data[0][1] if len(data[0]) > 1 else None
        last = data[-1][1] if len(data[-1]) > 1 else None
        return {"ok": True, "value_at_first": first, "value_at_last": last,
                "length": out.get("length")}

    @registry.tool(
        "cst_read_port_info_tool",
        "Read port mode information: cutoff frequency, wave impedance, effective permittivity.",
        CATEGORY_VERIFY,
        params={"cst_file": "str | null", "operating_frequency": "float | null"},
        examples=[{}, {"operating_frequency": 2.4}],
        returns="{cutoff_frequency, wave_impedance, effective_dielectric_constant, verdict}",
        notes=[
            "cutoff_frequency above the operating band means the mode is evanescent and the "
            "S-parameters cannot be trusted - use a discrete port instead.",
            "operating_frequency is optional. Without it the verdict is compared against the "
            "solver's own lower band edge, read from the project, so it is correct for any band.",
            "Values are in the project's frequency unit (GHz for HF projects).",
        ],
    )
    def read_port_info(cst_file: str | None = None,
                       operating_frequency: float | None = None) -> dict[str, Any]:
        paths = {
            "cutoff_frequency": "1D Results\\Port Information\\Cutoff Frequency\\1(1)",
            "wave_impedance": "1D Results\\Port Information\\Wave Impedance\\1(1)",
            "effective_dielectric_constant":
                "1D Results\\Port Information\\Effective Dielectric Constant\\1(1)",
        }
        out: dict[str, Any] = {"ok": True}
        for key, path in paths.items():
            try:
                res = s().read_result(path, cst_file=cst_file, max_points=5)
                data = res.get("data") or []
                out[key] = data[-1][1] if data and len(data[-1]) > 1 else (data[0] if data else None)
            except Exception as exc:  # noqa: BLE001
                out[key] = None
                out.setdefault("missing", []).append({"item": key, "error": str(exc)})
        cutoff = _to_float(out.get("cutoff_frequency"))

        # The verdict must compare the cutoff against THIS project's operating band.
        # A hardcoded threshold is wrong for any other band: a 77 GHz radar port has a
        # cutoff above 2 GHz yet is perfectly propagating. Prefer the caller's stated
        # operating frequency, otherwise read the solver band from the project.
        reference = operating_frequency
        reference_source = "operating_frequency argument"
        band = None
        if reference is None:
            try:
                band = _solver_band()
            except Exception:  # noqa: BLE001 - a band read must never fail the whole tool
                band = None
            if band is not None:
                reference = band[0]
                reference_source = "solver lower band edge (Solver.GetFmin)"

        if cutoff is None:
            out["verdict"] = ("no port mode information (is this a discrete port? "
                              "then ZRef is authoritative)")
        elif reference is None:
            out["verdict"] = (
                "UNKNOWN: cutoff frequency present but no operating frequency was given "
                "and the solver band could not be read; compare cutoff_frequency against "
                "your band yourself"
            )
        elif cutoff >= reference:
            out["verdict"] = (
                f"WARNING: cutoff {cutoff} is not below the lowest operating frequency "
                f"{reference} - the port mode is evanescent in your band and the "
                f"S-parameters cannot be trusted; use a discrete port instead"
            )
        else:
            out["verdict"] = (
                f"OK: cutoff {cutoff} is below the lowest operating frequency {reference} "
                f"({round(100 * (1 - cutoff / reference), 1)}% margin)"
            )

        if reference is not None:
            out["reference_frequency"] = reference
            out["reference_source"] = reference_source
        if band is not None:
            out["solver_band"] = list(band)
        return out

    @registry.tool(
        "cst_energy_summary_tool",
        "Report the power budget and efficiencies at a frequency (radiated / accepted / losses).",
        CATEGORY_VERIFY, params={"frequency": "float", "cst_file": "str | null"},
        examples=[{"frequency": 2.4}],
        returns="{efficiencies, powers}",
        notes=[
            "Total efficiency is radiated/stimulated and includes all losses (e.g. lossy substrate).",
            "Radiation efficiency is radiated/accepted.",
        ],
    )
    def energy_summary(frequency: float = 2.4, cst_file: str | None = None) -> dict[str, Any]:
        wanted = {
            "total_efficiency": "1D Results\\Efficiencies\\Tot. Efficiency [1]",
            "radiation_efficiency": "1D Results\\Efficiencies\\Rad. Efficiency [1]",
            "power_radiated": "1D Results\\Power\\Excitation [1]\\Power Radiated",
            "power_accepted": "1D Results\\Power\\Excitation [1]\\Power Accepted",
            "power_stimulated": "1D Results\\Power\\Excitation [1]\\Power Stimulated",
            "loss_dielectrics": "1D Results\\Power\\Excitation [1]\\Loss in Dielectrics",
            "loss_metals": "1D Results\\Power\\Excitation [1]\\Loss in Metals",
        }
        out: dict[str, Any] = {"ok": True, "frequency": frequency}
        for key, path in wanted.items():
            try:
                res = s().read_result(path, cst_file=cst_file, max_points=200)
                data = res.get("data") or []
                if not data:
                    continue
                hit = _nearest(data, float(frequency)) or (None, None)
                value = _to_float(hit[1])
                out[key] = value
                if key.endswith("efficiency") and value:
                    out[key + "_percent"] = round(100 * value, 2)
                    if value > 0:
                        out[key + "_db"] = round(10 * math.log10(value), 2)
            except Exception:  # noqa: BLE001
                continue
        return out

    @registry.tool(
        "cst_model_audit_tool",
        "Audit the built model: solids, materials, volumes and bounding boxes.",
        CATEGORY_VERIFY, params={}, returns="{shape_count, shapes}",
        notes=[
            "Volume is the cheap independent check that a boolean actually happened:",
            "a brick with a slot cut out must have the smaller volume.",
        ],
        replaces_vba="Solid.GetNumberOfShapes / GetVolume / GetLooseBoundingBoxOfShape",
    )
    def model_audit_tool() -> dict[str, Any]:
        return model_audit()

    # ---------------------------------------------------------------- export
    @registry.tool(
        "cst_export_touchstone_tool",
        "Export the S-parameters as a Touchstone file at a chosen reference impedance.",
        CATEGORY_EXPORT,
        params={"filename": "str", "impedance": "float", "export_type": "str",
                "data_format": "str", "frequency_range": "str"},
        required=["filename"],
        examples=[{"filename": "C:\\CST_MCP_workspace\\evidence\\s11", "impedance": 50.0,
                   "data_format": "RI"}],
        returns="{filename} (no extension; CST adds .s1p / .s2p)",
        notes=["Solve the project first: export of an unsolved model fails with",
               "'TOUCHSTONE export calculation failed.'"],
        replaces_vba="TOUCHSTONE object (.FileName/.Impedance/.Write)",
    )
    def export_touchstone_tool(filename: str, impedance: float = 50.0, export_type: str = "S",
                               data_format: str = "RI", frequency_range: str = "Full") -> dict[str, Any]:
        return export_touchstone(filename=filename, impedance=impedance,
                                 export_type=export_type, data_format=data_format,
                                 frequency_range=frequency_range)

    @registry.tool(
        "cst_export_ascii_tool",
        "Export one result tree item to an ASCII/CSV file for external checking.",
        CATEGORY_EXPORT,
        params={"tree_path": "str", "filename": "str", "mode": "str"},
        required=["tree_path", "filename"],
        examples=[{"tree_path": "1D Results\\S-Parameters\\S1,1",
                   "filename": "C:\\CST_MCP_workspace\\evidence\\s11.txt", "mode": "RealImag"}],
        returns="{filename}",
        notes=["mode: RealImag | Magnitude | dB | Phase"],
        replaces_vba="SelectTreeItem + ASCIIExport",
    )
    def export_ascii(tree_path: str, filename: str, mode: str = "RealImag") -> dict[str, Any]:
        target = config.resolve_path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        # For 1D results the tree selection is the only selector; CST 2026.2 has
        # no SetSubset method and Mode applies to 2D/3D field results.
        lines = [
            f'SelectTreeItem ("{tree_path}")',
            "With ASCIIExport", " .Reset", f' .FileName ("{target}")',
            ' .SetFileType ("ascii")', " .Execute", "End With",
        ]
        errors = ""
        try:
            _sess().run_vba("\n".join(lines))
        except Exception as exc:  # noqa: BLE001
            errors = f"{type(exc).__name__}: {exc}"
        produced = target.is_file()
        if not produced and not errors:
            errors = "ASCIIExport reported no error but wrote no file"
        return {"ok": produced, "filename": str(target), "exists": produced,
                "mode_note": f"requested mode {mode!r} is ignored for 1D results by CST",
                "error": errors or None}

    @registry.tool(
        "cst_write_summary_json_tool",
        "Write a single JSON file summarising solver, frequency range, S11 and efficiencies.",
        CATEGORY_EXPORT, params={"out_path": "str", "target_frequency": "float"},
        required=["out_path"],
        examples=[{"out_path": "C:\\CST_MCP_workspace\\evidence\\result_summary.json",
                   "target_frequency": 2.4}],
        notes=["Intended as the hand-off artefact for another agent or for a report."],
    )
    def write_summary_json(out_path: str, target_frequency: float = 2.4) -> dict[str, Any]:
        summary: dict[str, Any] = {"target_frequency": target_frequency}
        with_error = False
        for key, fn in (
            ("s11", lambda: read_s11(target_frequency=target_frequency)),
            ("reference_impedance", lambda: read_zref()),
            ("port_info", lambda: read_port_info()),
            ("energy", lambda: energy_summary(frequency=target_frequency)),
            ("model", lambda: model_audit()),
        ):
            try:
                summary[key] = fn()
            except Exception as exc:  # noqa: BLE001
                summary[key] = {"error": f"{type(exc).__name__}: {exc}"}
                with_error = True
        target = config.resolve_path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
        return {"ok": not with_error, "out_path": str(target), "summary": summary}
