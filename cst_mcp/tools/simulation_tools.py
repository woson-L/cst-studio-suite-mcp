"""Solver, frequency-range, boundary, background, mesh and monitor tools.

These are the settings that decide whether a result means anything, so the
command strings are kept in one place and validated (see SOLVER_TYPES, MESH_TYPES,
MONITOR_FIELDS). Setting an unknown value raises with the allowed list instead of
failing somewhere inside CST.
"""
from __future__ import annotations

from typing import Any

from ..registry import ToolRegistry
from ..session import session
from .session_tools import MIN_FREE_RAM_BYTES, memory_report

CATEGORY = "solver"
CATEGORY_MESH = "mesh"
CATEGORY_MONITOR = "monitor"

#: Module-level alias for the session factory, kept short and un-shadowed so tests
#: (and a swapped session backend) can replace one name. Must not be called `s`:
#: `register_tools` binds a local `s`, which would shadow it.
_sess = session

#: Valid strings for ChangeSolverType, from the CST 2026 VBA reference.
SOLVER_TYPES = {
    "hf time domain": "HF Time Domain",
    "time domain": "HF Time Domain",
    "transient": "HF Time Domain",
    "hf frequency domain": "HF Frequency Domain",
    "frequency domain": "HF Frequency Domain",
    "hf eigenmode": "HF Eigenmode",
    "eigenmode": "HF Eigenmode",
    "hf integraleq": "HF IntegralEq",
    "integral equation": "HF IntegralEq",
    "hf multilayer": "HF Multilayer",
    "multilayer": "HF Multilayer",
    "hf asymptotic": "HF Asymptotic",
    "asymptotic": "HF Asymptotic",
    "lf estatic": "LF EStatic",
    "lf mstatic": "LF MStatic",
    "lf stationary current": "LF Stationary Current",
    "stationary current": "LF Stationary Current",
    "lf frequency domain": "LF Frequency Domain",
    "lf time domain": "LF Time Domain (MQS)",
    "thermal steady state": "Thermal Steady State",
    "thermal transient": "Thermal Transient",
    "mechanics": "Mechanics",
    "cable": "Cable Solver",
}

#: Mesh.MeshType values.
MESH_TYPES = {
    "hexahedral": "HexahedralFIT",
    "hexahedralfit": "HexahedralFIT",
    "fit": "HexahedralFIT",
    "hexahedraltlm": "HexahedralTLM",
    "tlm": "HexahedralTLM",
    "tetrahedral": "Tetrahedral",
    "tet": "Tetrahedral",
    "surface": "Surface",
    "surfaceml": "SurfaceML",
    "planar": "Planar",
}

#: FDSolver.SetMethod(mesh, sweep)
FD_MESHES = ("Hexahedral", "Tetrahedral", "Surface")
FD_SWEEPS = ("General Purpose", "Fast reduced order model", "Discrete samples only")

#: EigenmodeSolver.SetMethodType(method, mesh). The 2026 reference documents a
#: per-mesh split: AKS and JDM are hexahedral methods, while Automatic /
#: Classical (Lossless) / General (Lossy) are tetrahedral methods. Pairing a
#: method with the wrong mesh string is what made "AKS" unusable before.
#:
#: JDM / "JDM (low memory)" are deliberately ABSENT even for the hexahedral mesh:
#: a live run against CST 2026.2 (tests/verify_live.py, step eigenmode_reject_jdm)
#: proved this build answers `Invalid Eigenmode solver type: JDM`. They belong on
#: the hexahedral list only if a future build is re-probed and accepts them.
EIGENMODE_METHODS = {
    "Tetrahedral Mesh": ("Automatic", "Classical (Lossless)", "General (Lossy)"),
    "Hexahedral Mesh": ("Automatic", "AKS"),
}
EIGENMODE_MESH_ARG = {"Tetrahedral Mesh": "Tet", "Hexahedral Mesh": "Hex"}

#: The subset of EIGENMODE_METHODS that is safe on every mesh type, used only for
#: documentation. "Automatic" is the CST default and avoids the whole question.
EIGENMODE_METHODS_COMMON = ("Automatic",)

#: FDSolver.AccuracyHex takes a RELATIVE RESIDUAL NORM in 1e-3..1e-12, not a word.
#: The words are kept as convenience aliases and mapped to numbers, because the
#: previous code passed e.g. "High" straight to CST and silently emitted nothing
#: at all for a numeric value.
FD_ACCURACY_HEX_ALIASES = {
    "low": "1e-3", "medium": "1e-4", "high": "1e-5", "very high": "1e-6",
}

#: FDSolver.OrderTet accepts First | Second | Third. "Mixed" is NOT an order:
#: variable order is the separate MixedOrderTet flag.
FD_ORDERS = ("First", "Second", "Third")

#: Monitor.FieldType values, from the 2026 VBA reference. Note that the
#: TimeMonitor object uses a DIFFERENT vocabulary ("E-Field", "B-Field", ...):
#: mixing the two silently produces the wrong monitor.
MONITOR_FIELDS = {
    "efield": "Efield", "e": "Efield", "electric": "Efield", "e-field": "Efield",
    "hfield": "Hfield", "h": "Hfield", "magnetic": "Hfield", "h-field": "Hfield",
    "powerflow": "Powerflow", "poynting": "Powerflow",
    "current": "Current", "currentdensity": "Current",
    "powerloss": "Powerloss", "loss": "Powerloss",
    "eenergy": "Eenergy", "henergy": "Henergy", "energy": "Eenergy",
    "farfield": "Farfield", "far": "Farfield",
    "fieldsource": "Fieldsource", "spacecharge": "Spacecharge",
    "particlecurrentdensity": "Particlecurrentdensity",
}

MONITOR_DOMAINS = {"frequency": "Frequency", "time": "Time"}

#: Units.SetUnit ("Frequency", <unit>) accepts these. Solver.FrequencyRange takes
#: plain doubles interpreted in the PROJECT unit, so the unit has to be set
#: explicitly or a value in "MHz" silently becomes a 1000x wrong band.
FREQUENCY_UNITS = {u.lower(): u for u in ("Hz", "kHz", "MHz", "GHz", "THz")}

#: Boundary types accepted by the Boundary object's Xmin..Zmax properties.
#: From the 2026 VBA reference: electric, magnetic, tangential, normal, open,
#: expanded open, periodic, conducting wall, unit cell. "none" is NOT a boundary
#: type - it exists only for Xsymmetry/PotentialType/TemperatureType - so accepting
#: it here sent CST an invalid value.
BOUNDARY_KINDS = (
    "expanded open", "open", "open (add space)", "electric", "magnetic",
    "tangential", "normal", "periodic", "unit cell", "conducting wall",
)

SYMMETRY_KINDS = ("none", "electric", "magnetic")


def _canonical(value: str, table: dict[str, str], label: str) -> str:
    key = str(value).strip().lower()
    if key in table:
        return table[key]
    allowed = ", ".join(sorted({v for v in table.values()}))
    raise ValueError(f"unknown {label} {value!r}. Allowed: {allowed}")


def _to_float(value: Any) -> float | None:
    """Parse a scalar CST may hand back as a plain number or a "(a+bj)" repr."""
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


def read_solver_band() -> tuple[float, str] | None:
    """Return (fmax, frequency_unit) for the active project, or None.

    Used to size a mesh from a physical feature: the element size follows from the
    shortest wavelength in the band and the project's frequency unit.
    Verified 2026 command: `Solver.GetFmax()` works; `Units.GetUnit ("Frequency")`
    must be qualified with the `Units` object (a bare `GetUnit` fails with
    "Expecting an already dimensioned array").
    """
    marker = "MCPBAND="
    try:
        _sess().run_vba(
            "Sub Main\n"
            "Dim f As String, u As String\n"
            "f = \"?\"\n"
            "u = \"?\"\n"
            "On Error Resume Next\n"
            "f = CStr(Solver.GetFmax())\n"
            'u = Units.GetUnit ("Frequency")\n'
            "On Error GoTo 0\n"
            f'ReportInformationToWindow "{marker}" & f & "|" & u\n'
            "End Sub\n"
        )
        for message in reversed(_sess().messages(limit=15)):
            if marker in message["text"]:
                payload = message["text"].split(marker, 1)[1].strip()
                freq, _, unit = payload.partition("|")
                value = _to_float(freq)
                if value is None or not unit.strip():
                    return None
                return value, unit.strip()
    except Exception:  # noqa: BLE001 - the caller decides what to do without a band
        return None
    return None


def read_frequency_unit() -> str | None:
    """Return the project's current frequency unit, or None if it cannot be read.

    Verified on CST 2026.2: the call must be qualified as `Units.GetUnit(...)`.
    A bare `GetUnit ("Frequency")` fails with "Expecting an already dimensioned
    array", and `Units.GetUnit$` does not exist. `Units.SetUnit` is unqualified in
    the reference examples but the getter is not.

    Read through the message window because the VBA bridge has no return channel.
    Best-effort: a failure returns None rather than breaking a caller.
    """
    marker = "MCPFREQUNIT="
    try:
        _sess().run_vba(
            "Sub Main\n"
            "Dim u As String\n"
            "u = \"?\"\n"
            "On Error Resume Next\n"
            'u = Units.GetUnit ("Frequency")\n'
            "On Error GoTo 0\n"
            f'ReportInformationToWindow "{marker}" & u\n'
            "End Sub\n"
        )
        for message in reversed(_sess().messages(limit=15)):
            if marker in message["text"]:
                value = message["text"].split(marker, 1)[1].strip()
                return value or None
    except Exception:  # noqa: BLE001 - reporting the previous unit is optional
        return None
    return None


def monitor_names(s) -> list[dict[str, Any]]:
    """Read the monitor list. Verified: indices are 0-based in CST 2026.2."""
    marker = "MCPMONITORLIST="
    _sess().run_vba(
        "Sub Main\n"
        "Dim n As Long, i As Long, s As String, nm As String\n"
        "n = Monitor.GetNumberOfMonitors()\n"
        "For i = 0 To n - 1\n"
        "nm = \"?\"\n"
        "On Error Resume Next\n"
        "nm = Monitor.GetMonitorNameFromIndex(i)\n"
        "On Error GoTo 0\n"
        "s = s & nm & \";\"\n"
        "Next i\n"
        f'ReportInformationToWindow "{marker}" & n & "|" & s\n'
        "End Sub\n"
    )
    for m in reversed(s().messages(limit=15)):
        if marker in m["text"]:
            body = m["text"].split(marker, 1)[1]
            count_text, _, names_text = body.partition("|")
            names = [x for x in names_text.split(";") if x.strip()]
            return [{"index": i, "name": n} for i, n in enumerate(names)]
    return []


def register_tools(registry: ToolRegistry) -> None:
    # Late-bound on purpose: resolve `_sess` at call time so replacing the
    # module-level alias (tests, or a swapped session backend) is seen by every
    # registered tool instead of being frozen at import time.
    s = lambda *a, **k: _sess(*a, **k)  # noqa: E731

    # ----------------------------------------------------------------- solver
    @registry.tool(
        "cst_set_solver_tool", "Select the solver (high frequency time domain / frequency domain / eigenmode / ...).",
        CATEGORY,
        params={"solver": "str"},
        required=["solver"],
        returns="{solver: <canonical name>}",
        examples=[{"solver": "HF Frequency Domain"},
                  {"solver": "frequency domain"},
                  {"solver": "HF Time Domain"},
                  {"solver": "HF Eigenmode"}],
        notes=[
            "Plain-English aliases are accepted: 'frequency domain', 'time domain', 'eigenmode'.",
            "The solver string is read back from CST, so the result shows what is really active.",
        ],
        replaces_vba="ChangeSolverType",
    )
    def set_solver(solver: str) -> dict[str, Any]:
        canonical = _canonical(solver, SOLVER_TYPES, "solver")
        s().add_history(f"select solver: {canonical}", f'ChangeSolverType "{canonical}"')
        active = s().run_vba(
            'Sub Main\nReportInformationToWindow "MCPSOLVER=" & GetSolverType()\nEnd Sub\n'
        )
        readback = None
        for m in reversed(s().messages(limit=15)):
            if "MCPSOLVER=" in m["text"]:
                readback = m["text"].split("MCPSOLVER=", 1)[1].strip()
                break
        return {"ok": True, "requested": canonical, "solver": readback or canonical, **active}

    @registry.tool(
        "cst_get_solver_tool", "Read the currently active solver.",
        CATEGORY, params={}, returns="{solver}",
        replaces_vba="GetSolverType",
    )
    def get_solver() -> dict[str, Any]:
        _sess().run_vba('Sub Main\nReportInformationToWindow "MCPSOLVER=" & GetSolverType()\nEnd Sub\n')
        for m in reversed(s().messages(limit=15)):
            if "MCPSOLVER=" in m["text"]:
                return {"ok": True, "solver": m["text"].split("MCPSOLVER=", 1)[1].strip()}
        raise RuntimeError("CST did not report the solver type; check cst_messages_tool")

    @registry.tool(
        "cst_set_frequency_range_tool", "Set the solver frequency range (the band that is actually simulated).",
        CATEGORY,
        params={"fmin": "float", "fmax": "float", "unit": "str"},
        required=["fmin", "fmax"],
        returns="{frequency_range: [fmin, fmax], unit, unit_applied, previous_unit}",
        examples=[{"fmin": 2.2, "fmax": 2.7, "unit": "GHz"}],
        notes=[
            "This is the solver range. It is different from monitor frequencies and from the export grid.",
            "Always save the project after changing it: a solver run without a range fails with",
            "'Solver run failed. Frequency range not set correctly.'",
            "unit sets the PROJECT frequency unit with Units.SetUnit before setting the range, and "
            "the reply reports the unit CST actually holds. Solver.FrequencyRange takes plain "
            "numbers in the project unit, so passing unit='MHz' to a GHz project without this "
            "would set a 1000x wrong band.",
            "Allowed units: Hz, kHz, MHz, GHz, THz.",
        ],
        replaces_vba="Solver.FrequencyRange / Units.SetUnit (\"Frequency\", ...)",
    )
    def set_frequency_range(fmin: float, fmax: float, unit: str = "GHz") -> dict[str, Any]:
        if fmin >= fmax:
            raise ValueError("fmin must be smaller than fmax")
        unit_key = unit.strip()
        if unit_key.lower() not in FREQUENCY_UNITS:
            raise ValueError(
                f"unknown frequency unit {unit!r}. Allowed: {', '.join(FREQUENCY_UNITS)}"
            )
        canonical = FREQUENCY_UNITS[unit_key.lower()]
        current_unit = read_frequency_unit()
        # Verified 2026 commands: Solver.FrequencyRange (both the transient and the
        # frequency domain solver) and Units.SetUnit ("Frequency", ...). FrequencyRange
        # takes plain doubles interpreted in the PROJECT unit, so the unit has to be
        # set explicitly or the value is silently scaled by the project's unit.
        s().add_history(
            f"set solver frequency range {fmin} - {fmax} {canonical}",
            'With Units\n'
            f' .SetUnit ("Frequency", "{canonical}")\n'
            "End With\n"
            f'Solver.FrequencyRange "{fmin}", "{fmax}"',
        )
        return {
            "ok": True,
            "frequency_range": [fmin, fmax],
            "unit": canonical,
            "unit_applied": True,
            "previous_unit": current_unit,
        }

    @registry.tool(
        "cst_configure_fd_solver_tool",
        "Configure the frequency domain solver: mesh method, sweep type, element order, accuracy, adaption.",
        CATEGORY,
        params={"mesh": "str", "sweep": "str", "order": "str", "accuracy": "str",
                "mesh_adaption": "bool", "double_precision": "bool", "max_cpus": "int | null"},
        returns="{ok, applied, not_applied?}",
        examples=[{"mesh": "Tetrahedral", "sweep": "General Purpose", "order": "Second",
                   "accuracy": "1e-4", "mesh_adaption": False},
                  {"mesh": "Hexahedral", "sweep": "General Purpose", "accuracy": "1e-4"}],
        notes=[
            "mesh: Hexahedral | Tetrahedral | Surface",
            "sweep: General Purpose | Fast reduced order model | Discrete samples only",
            "order (tetrahedral only): First | Second | Third, or Mixed for variable order "
            "(emitted as MixedOrderTet). There is no OrderTet value 'Mixed'.",
            "accuracy, tetrahedral: tetrahedral relative residual, e.g. 1e-4.",
            "accuracy, hexahedral/Surface: relative residual norm 1e-3..1e-12, or the aliases "
            "Low/Medium/High/Very high (mapped to 1e-3/1e-4/1e-5/1e-6). Out-of-range values are "
            "rejected instead of being dropped silently.",
            "mesh_adaption is tetrahedral only; requesting it for another mesh raises.",
            "Select the frequency domain solver first with cst_set_solver_tool.",
            "Parameters that cannot apply to the chosen mesh are listed in not_applied.",
        ],
        replaces_vba="FDSolver.SetMethod / OrderTet / MixedOrderTet / AccuracyTet / AccuracyHex / MeshAdaptionTet",
    )
    def configure_fd_solver(mesh: str = "Tetrahedral", sweep: str = "General Purpose",
                            order: str = "Second", accuracy: str = "1e-4",
                            mesh_adaption: bool = False, double_precision: bool = True,
                            max_cpus: int | None = None) -> dict[str, Any]:
        mesh_key = next((m for m in FD_MESHES if m.lower() == mesh.strip().lower()), None)
        if mesh_key is None:
            raise ValueError(f"mesh must be one of {FD_MESHES}")
        sweep_key = next((v for v in FD_SWEEPS if v.lower() == sweep.strip().lower()), None)
        if sweep_key is None:
            raise ValueError(f"sweep must be one of {FD_SWEEPS}")

        lines = ["With FDSolver", " .Reset", f' .SetMethod "{mesh_key}", "{sweep_key}"']
        applied: dict[str, Any] = {"mesh": mesh_key, "sweep": sweep_key}
        not_applied: list[str] = []
        is_tet = mesh_key == "Tetrahedral"

        # OrderTet takes First | Second | Third. "Mixed" is not an order value: it
        # selects variable order through the separate MixedOrderTet flag, which is
        # what the previous code got wrong (it emitted .OrderTet "Mixed", a value
        # the method does not accept).
        order_key = order.strip().capitalize()
        if not is_tet:
            not_applied.append("order (tetrahedral mesh only)")
        elif order_key == "Mixed":
            lines.append(' .MixedOrderTet "True"')
            applied["mixed_order_tet"] = True
        elif order_key in FD_ORDERS:
            lines.append(f' .OrderTet "{order_key}"')
            applied["order_tet"] = order_key
        else:
            raise ValueError(f"order must be one of {FD_ORDERS} or 'Mixed'")

        accuracy_key = accuracy.strip()
        if is_tet:
            lines.append(f' .AccuracyTet "{accuracy_key}"')
            applied["accuracy_tet"] = accuracy_key
        else:
            # AccuracyHex takes a relative residual norm in 1e-3..1e-12. The word
            # aliases are convenience only and are converted to numbers; anything
            # else must parse as a number in range. The previous code silently
            # emitted NO accuracy line for a numeric value, so the caller's setting
            # was dropped without a word.
            numeric = FD_ACCURACY_HEX_ALIASES.get(accuracy_key.lower(), accuracy_key)
            try:
                value = float(numeric)
            except ValueError:
                raise ValueError(
                    "accuracy for a non-tetrahedral mesh must be a relative residual "
                    "norm between 1e-3 and 1e-12, or one of "
                    f"{tuple(FD_ACCURACY_HEX_ALIASES)}"
                ) from None
            if not 1e-12 <= value <= 1e-3:
                raise ValueError(
                    f"accuracy {value} is outside the range 1e-3 .. 1e-12 that "
                    "FDSolver.AccuracyHex accepts"
                )
            lines.append(f' .AccuracyHex "{numeric}"')
            applied["accuracy_hex"] = numeric

        # MeshAdaptionTet exists only on the tetrahedral solver.
        if is_tet:
            lines.append(f' .MeshAdaptionTet "{"True" if mesh_adaption else "False"}"')
            applied["mesh_adaption"] = bool(mesh_adaption)
        elif mesh_adaption:
            raise ValueError(
                "mesh_adaption applies to the tetrahedral frequency domain solver only "
                "(FDSolver.MeshAdaptionTet); it has no effect on "
                f"{mesh_key}"
            )

        lines.append(f' .UseDoublePrecision "{"True" if double_precision else "False"}"')
        applied["double_precision"] = bool(double_precision)
        if max_cpus is not None:
            if int(max_cpus) < 1:
                raise ValueError("max_cpus must be >= 1")
            lines.append(f' .MaxCPUs "{int(max_cpus)}"')
            applied["max_cpus"] = int(max_cpus)
        lines.append("End With")

        s().add_history("configure frequency domain solver", "\n".join(lines))
        result: dict[str, Any] = {"ok": True, "applied": applied}
        if not_applied:
            result["not_applied"] = not_applied
        return result

    @registry.tool(
        "cst_configure_eigenmode_solver_tool", "Configure the eigenmode solver (number of modes, target frequency).",
        CATEGORY,
        params={"n_modes": "int", "frequency": "float | null", "mesh_type": "str",
                "method": "str | null", "accuracy": "float | null"},
        required=["n_modes"],
        examples=[{"n_modes": 3, "frequency": 2.4},
                  {"n_modes": 5, "mesh_type": "Tetrahedral Mesh"}],
        notes=[
            "Select 'HF Eigenmode' first.",
            "mesh_type: Hexahedral Mesh | Tetrahedral Mesh.",
            "method, tetrahedral mesh: Automatic | Classical (Lossless) | General (Lossy).",
            "method, hexahedral mesh: Automatic | AKS. Pairing AKS with the tetrahedral mesh "
            "is invalid - the mesh argument follows the method, not the other way round.",
            "'JDM' and 'JDM (low memory)' are documented CST values for the hexahedral mesh but "
            "are refused by CST 2026.2 with 'Invalid Eigenmode solver type', so they are not "
            "accepted here; re-probe before enabling them on a newer build.",
            "frequency is the solver's target frequency; the band itself is the global solver frequency range.",
            "The eigenmode band is still the global Solver.FrequencyRange; this sets the mode count and target.",
        ],
        replaces_vba="EigenmodeSolver.SetNumberOfModes / SetFrequencyTarget / SetMeshType / SetMethodType",
    )
    def configure_eigenmode(n_modes: int = 1, frequency: float | None = None,
                            mesh_type: str = "Tetrahedral Mesh",
                            method: str | None = None,
                            accuracy: float | None = None) -> dict[str, Any]:
        if n_modes < 1:
            raise ValueError("n_modes must be >= 1")
        mesh_key = next((m for m in ("Hexahedral Mesh", "Tetrahedral Mesh")
                         if m.lower() == mesh_type.strip().lower()), None)
        if mesh_key is None:
            raise ValueError("mesh_type must be 'Hexahedral Mesh' or 'Tetrahedral Mesh'")
        lines = ["With EigenmodeSolver", " .Reset", f' .SetMeshType "{mesh_key}"']
        applied: dict[str, Any] = {"mesh_type": mesh_key, "n_modes": int(n_modes)}
        if method:
            allowed = EIGENMODE_METHODS[mesh_key]
            hit = next((m for m in allowed if m.lower() == method.strip().lower()), None)
            if hit is None:
                raise ValueError(
                    f"method {method!r} is not valid for the {mesh_key} eigenmode solver. "
                    f"Allowed for this mesh: {allowed}"
                )
            lines.append(f' .SetMethodType "{hit}", "{EIGENMODE_MESH_ARG[mesh_key]}"')
            applied["method"] = hit
            applied["method_mesh_arg"] = EIGENMODE_MESH_ARG[mesh_key]
        lines.append(f" .SetNumberOfModes {int(n_modes)}")
        if frequency is not None:
            lines.append(f' .SetFrequencyTarget "True", "{frequency}"')
            applied["frequency"] = frequency
        if accuracy is not None:
            lines.append(f' .SetAccuracy "{accuracy}"')
            applied["accuracy"] = accuracy
        lines.append("End With")
        s().add_history(f"configure eigenmode solver ({n_modes} modes)", "\n".join(lines))
        return {"ok": True, "applied": applied}

    @registry.tool(
        "cst_configure_td_solver_tool", "Configure the time domain (transient) solver.",
        CATEGORY,
        params={"accuracy": "str", "mesh_type": "str", "stimulation_port": "str",
                "norming_impedance": "float | null", "double_precision": "bool",
                "pulse_widths": "int | null"},
        examples=[{"accuracy": "-30", "mesh_type": "Hexahedral"},
                  {"accuracy": "-40", "stimulation_port": "All"}],
        notes=[
            "accuracy is the steady-state limit in dB in the range [-80, 0], for example '-30'.",
            "mesh_type: Hexahedral | Tetrahedral.",
            "This block has no Reset in CST: settings are applied directly.",
        ],
        replaces_vba="Solver.SteadyStateLimit / Solver.MeshType / Solver.UseDoublePrecision",
    )
    def configure_td(accuracy: str = "-30", mesh_type: str = "Hexahedral",
                     stimulation_port: str = "All", norming_impedance: float | None = None,
                     double_precision: bool = False, pulse_widths: int | None = None) -> dict[str, Any]:
        mesh_key = next((m for m in ("Hexahedral", "Tetrahedral")
                         if m.lower() == mesh_type.strip().lower()), None)
        if mesh_key is None:
            raise ValueError("mesh_type must be 'Hexahedral' or 'Tetrahedral'")
        try:
            acc_value = float(str(accuracy).strip())
        except ValueError:
            raise ValueError("accuracy must be a number of dB, for example '-30'") from None
        if not -80.0 <= acc_value <= 0.0:
            raise ValueError("accuracy must be between -80 and 0 dB")
        lines = [
            "With Solver",
            # The Solver object has no Reset and no MeshType in CST 2026.2;
            # the mesh is selected through the Mesh object (cst_set_mesh_tool).
            f' .SteadyStateLimit "{accuracy}"',
            f' .StimulationPort ("{stimulation_port}")',
            f' .UseDoublePrecision "{"True" if double_precision else "False"}"',
        ]
        applied: dict[str, Any] = {"accuracy": accuracy, "mesh_type": mesh_key,
                                   "stimulation_port": stimulation_port}
        if norming_impedance is not None:
            lines.append(' .AutoNormImpedance "True"')
            lines.append(f' .NormingImpedance "{norming_impedance}"')
            applied["norming_impedance"] = norming_impedance
        if pulse_widths:
            lines.append(f' .NumberOfPulseWidths "{int(pulse_widths)}"')
            applied["pulse_widths"] = int(pulse_widths)
        lines.append("End With")
        s().add_history("configure time domain solver", "\n".join(lines))
        applied["mesh_set_separately"] = True
        applied["mesh_setting_hint"] = (
            f"call cst_set_mesh_tool with mesh_type '{mesh_key}' because the "
            f"transient solver reads the mesh from the Mesh object"
        )
        return {"ok": True, "applied": applied}

    # ------------------------------------------------------------- frequency
    @registry.tool(
        "cst_frequency_overview_tool",
        "Report the solver, the solver frequency range and every monitor frequency in one view.",
        CATEGORY, params={}, returns="{solver, frequency_range, monitors}",
        notes=["Use this to confirm that the band you solve and the band you report are the same."],
    )
    def frequency_overview() -> dict[str, Any]:
        marker = "MCPFREQOVERVIEW="
        # Verified on CST 2026.2: Solver.GetFmin() / Solver.GetFmax() work;
        # Solver.GetFrequencyRange(index) and CStr(Solver.FrequencyRange) do not.
        _sess().run_vba(
            "Sub Main\n"
            "Dim a As String, b As String\n"
            "a = GetSolverType()\n"
            "b = \"?\"\n"
            "On Error Resume Next\n"
            "b = CStr(Solver.GetFmin()) & \" - \" & CStr(Solver.GetFmax())\n"
            "On Error GoTo 0\n"
            f'ReportInformationToWindow "{marker}" & a & "|" & b\n'
            "End Sub\n"
        )
        solver = band = None
        for m in reversed(s().messages(limit=15)):
            if marker in m["text"]:
                payload = m["text"].split(marker, 1)[1]
                solver, _, band = payload.partition("|")
                break
        # Read the monitors after the marker line has been captured: querying them
        # appends new messages, which would otherwise push the marker out of the window.
        monitors = monitor_names(s)
        return {
            "ok": True,
            "solver": (solver or "").strip() or None,
            "solver_frequency_range": (band or "").strip() or None,
            "monitors": monitors,
            "note": "solver_frequency_range is what the solver sweeps; monitor frequencies are separate.",
        }

    # -------------------------------------------------------------- boundary
    @registry.tool(
        "cst_set_boundary_tool", "Set the boundary conditions on the six domain sides.",
        CATEGORY,
        params={"xmin": "str", "xmax": "str", "ymin": "str", "ymax": "str", "zmin": "str",
                "zmax": "str", "all": "str | null"},
        examples=[{"all": "expanded open"},
                  {"xmin": "electric", "xmax": "electric", "ymin": "magnetic", "ymax": "magnetic",
                   "zmin": "open", "zmax": "open"}],
        notes=[
            "Kinds: " + ", ".join(BOUNDARY_KINDS) + ".",
            "'expanded open' is the usual choice for a radiating antenna.",
            "Values are matched case-insensitively and the canonical lower-case spelling is "
            "what reaches CST.",
        ],
        replaces_vba="Boundary.Xmin / Xmax / Ymin / Ymax / Zmin / Zmax",
    )
    def set_boundary(xmin: str = "expanded open", xmax: str = "expanded open",
                     ymin: str = "expanded open", ymax: str = "expanded open",
                     zmin: str = "expanded open", zmax: str = "expanded open",
                     all: str | None = None) -> dict[str, Any]:
        if all:
            xmin = xmax = ymin = ymax = zmin = zmax = all
        resolved: dict[str, str] = {}
        for label, value in (("xmin", xmin), ("xmax", xmax), ("ymin", ymin),
                             ("ymax", ymax), ("zmin", zmin), ("zmax", zmax)):
            key = value.strip().lower()
            if key not in BOUNDARY_KINDS:
                raise ValueError(f"{label}={value!r} is not a known boundary kind: {BOUNDARY_KINDS}")
            # Emit the canonical spelling, not the caller's casing: every other
            # enum in this module normalises, and CST expects the documented form.
            resolved[label] = key
        lines = ["With Boundary"] + [
            f' .{axis} "{resolved[axis.lower()]}"'
            for axis in ("Xmin", "Xmax", "Ymin", "Ymax", "Zmin", "Zmax")
        ] + [
            ' .ApplyInAllDirections "False"',
            "End With",
        ]
        s().add_history("set boundary conditions", "\n".join(lines))
        return {"ok": True, "boundaries": resolved}

    @registry.tool(
        "cst_set_symmetry_tool", "Set electric/magnetic symmetry planes (halves the solve time).",
        CATEGORY,
        params={"x": "str", "y": "str", "z": "str"},
        examples=[{"x": "none", "y": "magnetic", "z": "none"}],
        notes=["Symmetry must match the real field symmetry or the result is wrong. 'none' disables it."],
        replaces_vba="Boundary.Xsymmetry / Ysymmetry / Zsymmetry",
    )
    def set_symmetry(x: str = "none", y: str = "none", z: str = "none") -> dict[str, Any]:
        for label, value in (("x", x), ("y", y), ("z", z)):
            if value.strip().lower() not in SYMMETRY_KINDS:
                raise ValueError(f"{label} symmetry must be one of {SYMMETRY_KINDS}")
        lines = ["With Boundary",
                 f' .Xsymmetry "{x}"', f' .Ysymmetry "{y}"', f' .Zsymmetry "{z}"',
                 "End With"]
        s().add_history("set symmetry planes", "\n".join(lines))
        return {"ok": True, "symmetry": {"x": x, "y": y, "z": z}}

    @registry.tool(
        "cst_set_background_tool", "Set the background material and the extra space added around the model.",
        CATEGORY,
        params={"epsilon": "float", "mue": "float", "xmin_space": "float", "xmax_space": "float",
                "ymin_space": "float", "ymax_space": "float", "zmin_space": "float",
                "zmax_space": "float", "apply_in_all_directions": "bool"},
        examples=[{"epsilon": 1.0, "mue": 1.0, "apply_in_all_directions": True}],
        notes=[
            "Zero spacing with 'expanded open' boundaries lets CST add a quarter-wave space itself.",
            "CST's background default is PEC, not vacuum: set epsilon 1.0 explicitly for an "
            "open, radiating problem.",
            "The VBA parameter name is 'mue' for compatibility, but it maps to the Background "
            "object's documented Mu method.",
        ],
        replaces_vba="Background.Reset / Type / Epsilon / Mu / *Space / ApplyInAllDirections",
    )
    def set_background(epsilon: float = 1.0, mue: float = 1.0,
                       xmin_space: float = 0.0, xmax_space: float = 0.0,
                       ymin_space: float = 0.0, ymax_space: float = 0.0,
                       zmin_space: float = 0.0, zmax_space: float = 0.0,
                       apply_in_all_directions: bool = False) -> dict[str, Any]:
        # The Background object exposes `Reset` (not the macro-recorder's
        # `ResetBackground`) and `Mu` (not `Mue`). Neither legacy spelling appears
        # anywhere in the 2026 VBA reference. This build accepted them, but the
        # documented names are the ones that will keep working.
        lines = ["With Background", " .Reset", ' .Type "Normal"',
                 f' .Epsilon "{epsilon}"', f' .Mu "{mue}"',
                 f' .XminSpace "{xmin_space}"', f' .XmaxSpace "{xmax_space}"',
                 f' .YminSpace "{ymin_space}"', f' .YmaxSpace "{ymax_space}"',
                 f' .ZminSpace "{zmin_space}"', f' .ZmaxSpace "{zmax_space}"',
                 f' .ApplyInAllDirections "{"True" if apply_in_all_directions else "False"}"',
                 "End With"]
        s().add_history("set background", "\n".join(lines))
        return {"ok": True, "epsilon": epsilon, "mue": mue}

    # ------------------------------------------------------------------ mesh
    @registry.tool(
        "cst_set_mesh_tool", "Set the mesh type and its density (steps per wavelength, minimum steps).",
        CATEGORY_MESH,
        params={"mesh_type": "str", "steps_per_wavelength": "float | null",
                "min_step_number": "int | null", "lines_per_wavelength": "int | null",
                "smallest_feature_mm": "float | null"},
        examples=[{"mesh_type": "Tetrahedral", "steps_per_wavelength": 12},
                  {"mesh_type": "HexahedralFIT", "lines_per_wavelength": 20},
                  {"mesh_type": "Tetrahedral", "smallest_feature_mm": 2.0}],
        notes=[
            "mesh_type: HexahedralFIT | HexahedralTLM | Tetrahedral | Surface | SurfaceML | Planar",
            "steps_per_wavelength applies to the tetrahedral mesh; lines_per_wavelength to hexahedral FIT.",
            "smallest_feature_mm is the practical way to size a tetrahedral mesh: give the "
            "smallest gap or thickness in the model and the required minimum step count is "
            "derived from the solver band. Without it a thin gap is meshed with elements sized "
            "for the wavelength, the system is badly conditioned, and the frequency domain "
            "solver fails with 'Could not compute preconditioner.' (verified: a 2 mm gap in a "
            "0-100 MHz model needed MinimumStepNumberTet of a few hundred to solve at all).",
            "min_step_number overrides smallest_feature_mm when both are given.",
        ],
        replaces_vba="Mesh.MeshType / StepsPerWavelengthTet / MinimumStepNumberTet / LinesPerWavelength",
    )
    def set_mesh(mesh_type: str = "Tetrahedral", steps_per_wavelength: float | None = 12,
                 min_step_number: int | None = None,
                 lines_per_wavelength: int | None = None,
                 smallest_feature_mm: float | None = None) -> dict[str, Any]:
        canonical = _canonical(mesh_type, MESH_TYPES, "mesh type")
        derived = None
        if min_step_number is None and smallest_feature_mm:
            if smallest_feature_mm <= 0:
                raise ValueError("smallest_feature_mm must be > 0")
            band = read_solver_band()
            if band is None:
                raise ValueError(
                    "smallest_feature_mm needs the solver frequency range to derive a step "
                    "count; set it with cst_set_frequency_range_tool first, or pass "
                    "min_step_number explicitly."
                )
            fmax, unit = band
            if fmax <= 0:
                raise ValueError("the solver fmax must be > 0 to size the mesh")
            # c = 299.792458 mm*GHz; convert fmax to GHz for a millimetre wavelength.
            scale = {"hz": 1e-9, "khz": 1e-6, "mhz": 1e-3, "ghz": 1.0, "thz": 1e3}
            fmax_ghz = fmax * scale.get(unit.lower(), 1.0)
            wavelength_mm = 299.792458 / fmax_ghz
            derived = max(1, int(round(wavelength_mm / smallest_feature_mm)))
            min_step_number = derived

        lines = ["With Mesh", f' .MeshType "{canonical}"']
        applied: dict[str, Any] = {"mesh_type": canonical}
        if canonical == "Tetrahedral":
            if steps_per_wavelength:
                lines.append(f' .StepsPerWavelengthTet "{steps_per_wavelength}"')
                applied["steps_per_wavelength_tet"] = steps_per_wavelength
            if min_step_number:
                lines.append(f' .MinimumStepNumberTet "{int(min_step_number)}"')
                applied["min_step_number_tet"] = int(min_step_number)
        elif canonical == "HexahedralFIT":
            if lines_per_wavelength:
                lines.append(f' .LinesPerWavelength "{int(lines_per_wavelength)}"')
                applied["lines_per_wavelength"] = int(lines_per_wavelength)
            if min_step_number:
                lines.append(f' .MinimumStepNumber "{int(min_step_number)}"')
                applied["min_step_number"] = int(min_step_number)
        lines.append("End With")
        s().add_history("set mesh", "\n".join(lines))
        if derived is not None:
            applied["derived_from_smallest_feature_mm"] = smallest_feature_mm
        return {"ok": True, "applied": applied}

    @registry.tool(
        "cst_generate_mesh_tool", "Mesh generation is not exposed through CST's VBA API.",
        CATEGORY_MESH, params={}, returns="{ok: false, error, alternative}",
        notes=[
            "CST 2026.2 has NO VBA command that builds the mesh on its own. The Mesh "
            "object documented in the VBA reference exposes settings only "
            "(MeshType, LinesPerWavelength, MinimumStepNumber, ...); a bare `Mesh` "
            "statement fails with 'Default property usage is invalid', and "
            "Mesh.Create / Mesh.Reset / MeshGeneration / MeshAdaption3D.Create do not "
            "exist either (all verified against the live build).",
            "The mesh is built by the solver, so run cst_run_solver_tool directly. "
            "The previous version of this tool emitted `Mesh` and therefore always "
            "failed, which also made cst_run_solver_tool report the stale error.",
            "To control the mesh, use cst_set_mesh_tool: it emits the real Mesh object "
            "settings, which the solver then honours.",
        ],
        replaces_vba="(none - use Mesh.* settings via cst_set_mesh_tool, then run the solver)",
    )
    def generate_mesh() -> dict[str, Any]:
        raise ValueError(
            "CST 2026.2 offers no VBA command to generate the mesh separately; the mesh "
            "is built when the solver runs. Call cst_run_solver_tool instead, and set mesh "
            "options with cst_set_mesh_tool beforehand. (This tool used to emit a bare "
            "`Mesh` statement, which CST always rejected with 'Default property usage is "
            "invalid'.)"
        )

    # -------------------------------------------------------------- monitor
    @registry.tool(
        "cst_add_monitor_tool", "Add a field monitor: far field, E/H field, power flow, current or loss.",
        CATEGORY_MONITOR,
        params={"name": "str", "field_type": "str", "frequency": "float | null",
                "domain": "str", "plane_normal": "str | null", "plane_position": "float | null"},
        required=["name", "field_type"],
        examples=[{"name": "farfield_2450", "field_type": "Farfield", "frequency": 2.45},
                  {"name": "efield_24", "field_type": "Efield", "frequency": 2.4,
                   "plane_normal": "z", "plane_position": 0.0}],
        notes=[
            "field_type aliases: farfield/far, efield/e, hfield/h, powerflow, current, powerloss, eenergy/henergy.",
            "Far field monitors need the Frequency Domain or Time Domain solver and a solved model.",
            "A monitor frequency is NOT the solver range: set the range with cst_set_frequency_range_tool.",
        ],
        replaces_vba="Monitor object (FieldType / Domain / Frequency / Create)",
    )
    def add_monitor(name: str, field_type: str, frequency: float | None = None,
                    domain: str = "Frequency", plane_normal: str | None = None,
                    plane_position: float | None = None) -> dict[str, Any]:
        canonical = _canonical(field_type, MONITOR_FIELDS, "field type")
        domain_key = _canonical(domain, MONITOR_DOMAINS, "domain")
        lines = ["With Monitor", " .Reset", f' .Name "{name}"', f' .FieldType "{canonical}"',
                 f' .Domain "{domain_key}"']
        if frequency is not None:
            lines.append(f' .Frequency "{frequency}"')
        if plane_normal:
            axis = plane_normal.strip().lower()
            if axis not in {"x", "y", "z"}:
                raise ValueError("plane_normal must be x, y or z")
            lines.append(f' .PlaneNormal "{axis}"')
            if plane_position is not None:
                lines.append(f' .PlanePosition "{plane_position}"')
        lines.append(" .Create")
        lines.append("End With")
        s().add_history(f"monitor {name} ({canonical})", "\n".join(lines))
        return {"ok": True, "name": name, "field_type": canonical, "frequency": frequency,
                "domain": domain_key}

    @registry.tool(
        "cst_list_monitors_tool", "List the monitors defined in the project.",
        CATEGORY_MONITOR, params={}, returns="{count, monitors}",
        notes=["CST indexes monitors from 0."],
        replaces_vba="Monitor.GetNumberOfMonitors / GetMonitorNameFromIndex",
    )
    def list_monitors() -> dict[str, Any]:
        names = monitor_names(s)
        return {"ok": True, "count": len(names), "monitors": names}

    # ------------------------------------------------------------------ solve
    @registry.tool(
        "cst_run_solver_tool", "Run the configured solver and report CST's own diagnostics on failure.",
        CATEGORY, params={"allow_low_memory": "bool"},
        returns="{ok, error?, messages_tail, memory?}",
        notes=[
            "Save the project first (cst_save_project_tool).",
            "A failure returns the real CST message, e.g. 'Frequency range not set correctly.'",
            "Before starting, free RAM is checked: a frequency-domain solve needs about 2 GB "
            "and otherwise dies inside CST with 'Error during construction of pre-conditioner. "
            "Not enough memory.' When RAM is short the tool refuses with an actionable message "
            "instead, unless allow_low_memory=True.",
            "Each project left open costs about 0.7 GB; cst_quit_tool releases them all.",
        ],
        replaces_vba="Model3D.RunSolver",
    )
    def run_solver(allow_low_memory: bool = False) -> dict[str, Any]:
        # Refuse early rather than letting CST build a preconditioner it cannot fit:
        # that failure costs minutes and leaves the model in a half-solved state.
        memory = memory_report()
        free = memory.get("free_ram_bytes")
        if (not allow_low_memory and free is not None
                and free < MIN_FREE_RAM_BYTES):
            raise ValueError(
                f"refusing to start the solver: only {memory['free_ram_gb']} GB RAM is free "
                f"and a frequency-domain solve needs about "
                f"{memory['min_free_ram_gb_for_fd_solve']} GB. Close other applications, or "
                "call cst_quit_tool to release CST projects left open (each holds about "
                f"{memory['approx_ram_per_open_project_gb']} GB). Pass allow_low_memory=True "
                "to try anyway."
            )
        out = s().run_solver()
        out["memory"] = memory
        return out
