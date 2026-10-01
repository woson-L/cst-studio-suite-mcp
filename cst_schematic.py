from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


def vba_string(value: str | Path) -> str:
    """Return a CST/VBA double-quoted string literal."""
    text = str(value).replace('"', '""')
    return f'"{text}"'


def vba_bool(value: bool) -> str:
    return "True" if value else "False"


def wrap_sub_main(vba_code: str) -> str:
    code = vba_code.strip()
    if not code:
        raise ValueError("vba_code must not be empty")
    if "sub main" in code.lower():
        return code
    return f"Sub Main\n{code}\nEnd Sub"


def block_component_port(component_type: str, name: str, port_index: int) -> tuple[str, str, int]:
    normalized = component_type.strip()
    if not normalized:
        normalized = "BLOCK"
    return normalized, name.strip(), int(port_index)


@dataclass(frozen=True)
class SchematicEndpoint:
    component_type: str
    name: str
    port_index: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SchematicEndpoint":
        return cls(
            component_type=str(value.get("component_type", "BLOCK")),
            name=str(value["name"]),
            port_index=int(value.get("port_index", 0)),
        )


class CSTSchematicVBA:
    """Small, verified CST Design Studio VBA builders."""

    BASIC_BLOCK_TYPES = {
        "resistor": "CircuitBasic\\Resistor",
        "capacitor": "CircuitBasic\\Capacitor",
        "inductor": "CircuitBasic\\Inductor",
        "diode": "CircuitSemi\\Diode",
        "schottky_diode": "CircuitSemi\\Schottky Diode",
        "zener_diode": "CircuitSemi\\Zener Diode",
        "ground": "Ground",
        "touchstone": "Touchstone",
        "spice": "SPICE",
        "mws": "CSTMWS",
        "mws_file": "CSTMWSFile",
        "simulation_project_reference": "SimulationProjectReference",
    }

    @classmethod
    def block(
        cls,
        name: str,
        block_type: str,
        x: int = 50000,
        y: int = 50000,
        rotation: int | float = 0,
        double_properties: dict[str, Any] | None = None,
        integer_properties: dict[str, Any] | None = None,
        string_properties: dict[str, Any] | None = None,
        local_units: dict[str, str] | None = None,
        file_path: str | None = None,
        relative_path: bool = False,
        cache_files: bool | None = None,
        simulation_task: str | None = None,
    ) -> str:
        resolved_type = cls.BASIC_BLOCK_TYPES.get(block_type.strip().lower(), block_type.strip())
        if not name.strip():
            raise ValueError("name must not be empty")
        if not resolved_type:
            raise ValueError("block_type must not be empty")

        lines = [
            "With Block",
            "    .Reset",
            f"    .Type({vba_string(resolved_type)})",
            f"    .Name({vba_string(name.strip())})",
        ]
        if file_path:
            lines.append(f"    .SetRelativePath({vba_bool(relative_path)})")
            lines.append(f"    .SetFile({vba_string(file_path)})")
        if simulation_task:
            lines.append(f"    .SetSimulationTask({vba_string(simulation_task)})")
        lines.append(f"    .Position({int(x)}, {int(y)})")
        if rotation:
            lines.append(f"    .Rotate({rotation})")
        lines.append("    .Create")
        for prop, unit in (local_units or {}).items():
            lines.append(f"    .SetLocalUnitForProperty({vba_string(prop)}, {vba_string(unit)})")
        for prop, value in (double_properties or {}).items():
            lines.append(f"    .SetDoubleProperty({vba_string(prop)}, {vba_string(str(value))})")
        for prop, value in (integer_properties or {}).items():
            lines.append(f"    .SetIntegerProperty({vba_string(prop)}, {vba_string(str(value))})")
        for prop, value in (string_properties or {}).items():
            lines.append(f"    .SetStringProperty({vba_string(prop)}, {vba_string(str(value))})")
        if cache_files is not None:
            lines.append(f"    .SetCacheFiles({vba_bool(cache_files)})")
        lines.append("End With")
        lines.append(f"ReportInformationToWindow({vba_string('created block ' + name.strip())})")
        return "\n".join(lines)

    @classmethod
    def resistor(cls, name: str, resistance: float | str, unit: str = "Ohm", x: int = 50000, y: int = 50000) -> str:
        return cls.block(
            name=name,
            block_type="resistor",
            x=x,
            y=y,
            double_properties={"Resistance": resistance},
            local_units={"Resistance": unit},
        )

    @classmethod
    def capacitor(cls, name: str, capacitance: float | str, unit: str = "pF", x: int = 50000, y: int = 50000) -> str:
        return cls.block(
            name=name,
            block_type="capacitor",
            x=x,
            y=y,
            rotation=90,
            double_properties={"Capacitance": capacitance},
            local_units={"Capacitance": unit},
        )

    @classmethod
    def inductor(cls, name: str, inductance: float | str, unit: str = "nH", x: int = 50000, y: int = 50000) -> str:
        return cls.block(
            name=name,
            block_type="inductor",
            x=x,
            y=y,
            double_properties={"Inductance": inductance},
            local_units={"Inductance": unit},
        )

    @classmethod
    def diode(cls, name: str, x: int = 50000, y: int = 50000, model_type_index: int | None = None) -> str:
        integer_properties = {}
        if model_type_index is not None:
            integer_properties["Model Type"] = model_type_index
        return cls.block(
            name=name,
            block_type="diode",
            x=x,
            y=y,
            integer_properties=integer_properties,
        )

    @classmethod
    def ground(cls, name: str, x: int = 50000, y: int = 50000) -> str:
        return cls.block(name=name, block_type="ground", x=x, y=y)

    @classmethod
    def external_port(
        cls,
        name: str,
        x: int = 50000,
        y: int = 50000,
        label: str | None = None,
        rotation: int | float = 0,
        number_of_ports: int | None = None,
        differential: bool | None = None,
        common_reference: bool | None = None,
    ) -> str:
        if not name.strip():
            raise ValueError("name must not be empty")
        lines = [
            "With ExternalPort",
            "    .Reset",
            f"    .Name({vba_string(name.strip())})",
        ]
        if number_of_ports is not None:
            lines.append(f"    .SetNumberOfPorts({int(number_of_ports)})")
        if differential is not None:
            lines.append(f"    .SetDifferential({vba_bool(differential)})")
        if common_reference is not None:
            lines.append(f"    .SetCommonReference({vba_bool(common_reference)})")
        lines.append(f"    .Position({int(x)}, {int(y)})")
        if rotation:
            lines.append(f"    .Rotate({rotation})")
        lines.append("    .Create")
        if label is not None:
            lines.append(f"    .SetLabel({vba_string(label)})")
        lines.append("End With")
        lines.append(f"ReportInformationToWindow({vba_string('created external port ' + name.strip())})")
        return "\n".join(lines)

    @classmethod
    def connect(cls, endpoints: list[SchematicEndpoint], net_name: str = "", create_new_subnet: bool = False) -> str:
        if len(endpoints) < 2:
            raise ValueError("at least two endpoints are required")
        max_index = len(endpoints) - 1
        variable_suffix = re.sub(r"[^A-Za-z0-9_]", "_", net_name or "auto")
        if not variable_suffix or variable_suffix[0].isdigit():
            variable_suffix = "net_" + variable_suffix
        variable_name = f"ComponentPorts_{variable_suffix}"
        generated_name_var = f"GeneratedNetName_{variable_suffix}"
        lines = [
            f"Dim {variable_name}({max_index}, 2) As Variant",
        ]
        for index, endpoint in enumerate(endpoints):
            lines.extend(
                [
                    f"{variable_name}({index}, 0) = {vba_string(endpoint.component_type.upper())}",
                    f"{variable_name}({index}, 1) = {vba_string(endpoint.name)}",
                    f"{variable_name}({index}, 2) = {int(endpoint.port_index)}",
                ]
            )
        lines.extend(
            [
                f"Dim {generated_name_var} As String",
                "With Net",
                "    .Reset",
                f"    {generated_name_var} = .AddComponentPorts(\"\", {variable_name}, {vba_bool(create_new_subnet)})",
                f"    If {vba_string(net_name)} <> \"\" Then .Rename {generated_name_var}, {vba_string(net_name)}",
                "    .Apply",
                "End With",
                f"ReportInformationToWindow({vba_string('connected ' + str(len(endpoints)) + ' schematic endpoints')})",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def frequency_sweep(
        cls,
        task_name: str = "SPara1",
        fmin: float | str = 0.0,
        fmax: float | str = 10.0,
        samples: int = 101,
        unit: str = "GHz",
        circuit_simulator: str = "cst",
        broadband_sweep: bool = False,
        update_existing: bool = True,
    ) -> str:
        if not task_name.strip():
            raise ValueError("task_name must not be empty")
        lines = [
            "With SimulationTask",
            "    .Reset",
            f"    .Name({vba_string(task_name.strip())})",
        ]
        if update_existing:
            lines.extend(
                [
                    "    If Not .DoesExist Then",
                    "        .Type(\"S-Parameters\")",
                    "        .Create",
                    "    End If",
                ]
            )
        else:
            lines.extend(
                [
                    "    .Type(\"S-Parameters\")",
                    "    .Create",
                ]
            )
        lines.extend(
            [
                f"    .SetLocalUnit(\"Frequency\", {vba_string(unit)})",
                "    .SetProperty(\"maximum frequency range\", \"False\")",
                f"    .SetProperty(\"fmin\", {vba_string(str(fmin))})",
                f"    .SetProperty(\"fmax\", {vba_string(str(fmax))})",
                f"    .SetSweepData({fmin}, {fmax}, {int(samples)})",
                f"    .SetProperty(\"circuit simulator\", {vba_string(circuit_simulator)})",
                f"    .SetProperty(\"broadband sweep\", {vba_string(vba_bool(broadband_sweep))})",
                "End With",
                f"ReportInformationToWindow({vba_string('configured frequency sweep ' + task_name.strip())})",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def parameter_sweep(
        cls,
        sweep_task_name: str,
        sequence_name: str,
        parameter_name: str,
        points: list[float | int | str],
        simulation_type: str = "",
        start: bool = False,
    ) -> str:
        if not points:
            raise ValueError("points must not be empty")
        point_string = " ; ".join(str(point) for point in points)
        lines = [
            f"StoreParameter {vba_string(parameter_name)}, {vba_string(str(points[0]))}",
            "With SimulationTask",
            "    .Reset",
            f"    .Name({vba_string(sweep_task_name)})",
            "    If Not .DoesExist Then",
            "        .Type(\"parameter sweep\")",
            "        .Create",
            "    End If",
            "End With",
            "With DSParameterSweep",
            f"    .SetSimulationType({vba_string(simulation_type or sweep_task_name)})",
            f"    .AddSequence({vba_string(sequence_name)})",
            f"    .AddParameter_ArbitraryPoints({vba_string(sequence_name)}, {vba_string(parameter_name)}, {vba_string(point_string)})",
        ]
        if start:
            lines.append("    .Start")
        lines.extend(
            [
                "End With",
                f"ReportInformationToWindow({vba_string('configured parameter sweep ' + sweep_task_name)})",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def import_spice_model(cls, spice_netlist: str, subcircuit_name: str = "", dialect: str = "Combined") -> str:
        if not spice_netlist.strip():
            raise ValueError("spice_netlist must not be empty")
        escaped = spice_netlist.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        expression = " & vbCrLf & ".join(vba_string(line) for line in escaped)
        return "\n".join(
            [
                f"ImportSPICEFromString({expression}, {vba_string(subcircuit_name)}, {vba_string(dialect)})",
                "ReportInformationToWindow(\"imported SPICE model\")",
            ]
        )
