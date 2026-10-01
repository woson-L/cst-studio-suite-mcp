"""Material and port tools.

Materials
---------
CST materials can come from the installed material library by name (for example
"FR-4 (lossy)", "Copper (annealed)", "PEC") or be defined explicitly. Defining
explicitly is safer for a reproducible report because the properties are then part
of the project rather than of the library version.

Ports
-----
The choice of port decides whether the S-parameters mean anything:

* A **waveguide port** is right when the structure really is a waveguide at the
  port plane. On a thin microstrip cross-section the port mode can be evanescent
  in the whole band - verified case: cutoff 51.9 GHz and a 6.2 kohm wave
  impedance at 2.4 GHz - and then S11 is meaningless even though the solver
  succeeds.
* A **discrete port** (SParameter, impedance given) is the safe choice for a
  lumped feed or a microstrip line, because the reference impedance is exactly
  what you specify.

`cst_read_port_info_tool` exists so the mode can be checked after the solve.
"""
from __future__ import annotations

from typing import Any

from ..registry import ToolRegistry
from ..session import session

CATEGORY_MATERIAL = "material"
CATEGORY_PORT = "port"

MATERIAL_TYPES = {
    "normal": "Normal",
    "lossy metal": "Lossy Metal",
    "lossymetal": "Lossy Metal",
    "lossy_metal": "Lossy Metal",
    "pec": "PEC",
    "anisotropic": "Anisotropic",
    "nonlinear": "Nonlinear",
    "corrugated wall": "Corrugated wall",
    "ohmic sheet": "Ohmic sheet",
    "tensor formula": "Tensor formula",
}

PORT_ORIENTATIONS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


def register_tools(registry: ToolRegistry) -> None:
    s = session

    # -------------------------------------------------------------- material
    @registry.tool(
        "cst_create_material_tool",
        "Define a material explicitly (permittivity, permeability, conductivity, loss tangent).",
        CATEGORY_MATERIAL,
        params={"name": "str", "material_type": "str", "epsilon": "float", "mue": "float",
                "sigma": "float", "tan_d": "float", "tan_d_freq": "float", "rho": "float",
                "colour": "list | null"},
        required=["name"],
        examples=[{"name": "FR4_substrate", "material_type": "Normal", "epsilon": 4.3,
                   "tan_d": 0.025, "tan_d_freq": 2.45},
                  {"name": "Copper_ant", "material_type": "Lossy metal", "sigma": 5.8e7}],
        notes=["Defining the material in the project makes the report reproducible;",
               "the library value can change between CST installations."],
        replaces_vba="Material object (.Name/.Type/.Epsilon/.Mu/.Sigma/.TanD/.Create)",
    )
    def create_material(name: str, material_type: str = "Normal", epsilon: float = 1.0,
                        mue: float = 1.0, sigma: float = 0.0, tan_d: float = 0.0,
                        tan_d_freq: float = 2.45, rho: float = 0.0,
                        colour: list | None = None) -> dict[str, Any]:
        key = material_type.strip().lower()
        canonical = MATERIAL_TYPES.get(key)
        if canonical is None:
            raise ValueError(f"material_type must be one of {sorted(set(MATERIAL_TYPES.values()))}")
        # Colour needs exactly three components: a short list used to raise a raw
        # IndexError from the indexing below, which is not a usable error message.
        if colour is not None and len(colour) != 3:
            raise ValueError(f"colour needs exactly [r, g, b], got {len(colour)} values")
        rgb = list(colour) if colour else [0.75, 0.75, 0.75]
        # Verified on CST 2026.2: the documented MaterialUnit(...) and Color(...)
        # spellings are rejected with "Invalid unit dimension type" / "no such
        # property or method". The working sequence uses FrqType and Colour, the
        # same commands CST's own shipped examples use.
        lines = [
            "With Material", " .Reset", f' .Name "{name}"', ' .Folder ""',
            ' .FrqType "hf"',
            f' .Type "{canonical}"',
            f' .Epsilon "{epsilon}"', f' .Mu "{mue}"', f' .Sigma "{sigma}"',
        ]
        if canonical != "Lossy Metal":
            lines.append(f' .TanD "{tan_d}"')
            lines.append(f' .TanDFreq "{tan_d_freq}"')
            lines.append(' .TanDGiven "True"')
            lines.append(' .TanDModel "ConstTanD"')
        lines.append(f' .Rho "{rho}"')
        lines.append(' .ThermalType "Normal"')
        lines.append(f' .Colour "{rgb[0]}", "{rgb[1]}", "{rgb[2]}"')
        lines.append(" .Create")
        lines.append("End With")
        s().add_history(f"define material {name}", "\n".join(lines))
        return {"ok": True, "material": name, "type": canonical, "epsilon": epsilon,
                "mue": mue, "sigma": sigma, "tan_d": tan_d}

    @registry.tool(
        "cst_assign_material_tool", "Assign an existing material to a solid.",
        CATEGORY_MATERIAL,
        params={"solid": "str", "material": "str"},
        required=["solid", "material"],
        examples=[{"solid": "board:substrate", "material": "FR4_substrate"}],
        notes=["`solid` must be a full CST name 'component:solid'."],
        replaces_vba="Solid.ChangeMaterial",
    )
    def assign_material(solid: str, material: str) -> dict[str, Any]:
        if ":" not in solid:
            raise ValueError("solid must be a full CST name such as 'board:substrate'")
        return s().add_history(f"assign {material} to {solid}",
                               f'Solid.ChangeMaterial "{solid}", "{material}"')

    @registry.tool(
        "cst_load_material_from_library_tool",
        "Add a material to the project from the CST material library.",
        CATEGORY_MATERIAL,
        params={"library_path": "str", "material_name": "str | null", "replace": "bool"},
        required=["library_path"],
        examples=[{"library_path": "FR-4 (lossy)", "material_name": "FR4_substrate"},
                  {"library_path": "Copper (annealed)"}],
        notes=[
            "library_path is the material name (or 'folder/material') as listed in the CST library.",
            "Verified on 2026.2: this is MaterialLibrary.LoadMaterialFromLibrary, not Material.LoadFromLibrary.",
            "material_name renames the loaded material inside the project. CST's loader always "
            "names the project material after the LIBRARY entry, so without this the requested "
            "name would silently not exist. Verified live: Material.Rename succeeds after "
            "LoadMaterialFromLibrary and the renamed material keeps its properties.",
            "The returned 'material' key is the name that really exists in the project - use it, "
            "not the library name, when assigning the material to a solid.",
        ],
        replaces_vba="MaterialLibrary.LoadMaterialFromLibrary / Material.Rename",
    )
    def load_from_library(library_path: str, material_name: str | None = None,
                          replace: bool = True) -> dict[str, Any]:
        # Accept both separators: the CST library UI shows backslashes, while this
        # tool documents a forward slash. Previously only "/" was split, so
        # "Substrates\\FR-4 (lossy)" sent the whole string as the material name.
        library_key = library_path.strip().strip("\\/")
        normalized = library_key.replace("\\", "/")
        folder, _, leaf = normalized.rpartition("/")
        lines = [
            "With MaterialLibrary",
            f' .LoadMaterialFromLibrary ("{leaf}", "{folder}", {"True" if replace else "False"})',
            "End With",
        ]
        # The loader names the project material after `leaf`, so a requested
        # material_name has to be applied as an explicit rename afterwards.
        final_name = leaf
        renamed = False
        if material_name and material_name.strip() and material_name.strip() != leaf:
            final_name = material_name.strip()
            lines.append(f'Material.Rename "{leaf}", "{final_name}"')
            renamed = True
        result = s().add_history(f"load material {normalized} from library", "\n".join(lines))
        return {
            **result,
            "library_path": normalized,
            "material": final_name,
            "library_material": leaf,
            "renamed": renamed,
            "folder": folder,
        }

    # ------------------------------------------------------------------ port
    @registry.tool(
        "cst_add_waveguide_port_tool",
        "Add a waveguide port on a plane of the calculation domain.",
        CATEGORY_PORT,
        params={"port_number": "int", "orientation": "str", "xrange": "list", "yrange": "list",
                "zrange": "list", "n_modes": "int", "label": "str | null",
                "reference_plane": "float", "on_boundary": "bool"},
        required=["port_number", "orientation", "xrange", "yrange", "zrange"],
        examples=[{"port_number": 1, "orientation": "zmin", "xrange": [-10, 10],
                   "yrange": [-5, 5], "zrange": [0, 0], "n_modes": 1}],
        notes=[
            "orientation is the feeding direction: 'xmin' means the port sits at the lower x "
            "boundary and feeds in +x.",
            "After solving, check cst_read_port_info_tool: if the cutoff frequency is above the "
            "band, the mode is evanescent and S-parameters are meaningless.",
        ],
        replaces_vba="Port object (.Orientation/.Coordinates/.Xrange/.Create)",
    )
    def add_waveguide_port(port_number: int, orientation: str, xrange: list, yrange: list,
                           zrange: list, n_modes: int = 1, label: str | None = None,
                           reference_plane: float = 0.0, on_boundary: bool = True) -> dict[str, Any]:
        orient = orientation.strip().lower()
        if orient not in PORT_ORIENTATIONS:
            raise ValueError(f"orientation must be one of {PORT_ORIENTATIONS}")
        for name_, values in (("xrange", xrange), ("yrange", yrange), ("zrange", zrange)):
            if len(values) != 2:
                raise ValueError(f"{name_} needs [min, max]")
        lines = [
            "With Port", " .Reset", f" .PortNumber ({int(port_number)})",
            f' .Label "{label or f"P{int(port_number)}"}"',
            f" .NumberOfModes ({int(n_modes)})",
            f' .Orientation ("{orient}")',
            ' .Coordinates ("Free")',
            f' .PortOnBound ({"True" if on_boundary else "False"})',
            ' .ClipPickedPortToBound (False)',
            ' .AdjustPolarization (False)',
            " .PolarizationAngle (0.0)",
            f" .ReferencePlaneDistance ({reference_plane})",
            " .TextSize (50)",
            " .TextMaxLimit (0)",
            ' .Shield ("none")',
            f' .Xrange ({xrange[0]}, {xrange[1]})',
            f' .Yrange ({yrange[0]}, {yrange[1]})',
            f' .Zrange ({zrange[0]}, {zrange[1]})',
            " .Create",
            "End With",
        ]
        s().add_history(f"waveguide port {port_number} ({orient})", "\n".join(lines))
        return {"ok": True, "port_number": int(port_number), "type": "waveguide",
                "orientation": orient, "modes": int(n_modes)}

    @registry.tool(
        "cst_add_discrete_port_tool",
        "Add a discrete S-parameter port with an explicit reference impedance (safe for microstrip feeds).",
        CATEGORY_PORT,
        params={"port_number": "int", "point1": "list", "point2": "list", "impedance": "float",
                "label": "str | null", "monitor": "bool"},
        required=["port_number", "point1", "point2"],
        examples=[{"port_number": 1, "point1": [-30, 0, -1.6], "point2": [-30, 0, 0.035],
                   "impedance": 50.0}],
        notes=[
            "point1/point2 are the two ends of the port, normally across the substrate height "
            "between the ground plane and the conductor.",
            "The S-parameters are then referenced to exactly `impedance` - check it with "
            "cst_read_reference_impedance_tool.",
        ],
        replaces_vba="DiscretePort object (.Type/.Impedance/.SetP1/.SetP2/.Create)",
    )
    def add_discrete_port(port_number: int, point1: list, point2: list, impedance: float = 50.0,
                          label: str | None = None, monitor: bool = True) -> dict[str, Any]:
        for name_, point in (("point1", point1), ("point2", point2)):
            if len(point) != 3:
                raise ValueError(f"{name_} needs [x, y, z]")
        lines = [
            "With DiscretePort", " .Reset",
            f' .PortNumber "{int(port_number)}"',
            f' .Label "{label or f"P{int(port_number)}"}"',
            ' .Type "SParameter"',
            f' .Impedance "{impedance}"',
            f' .SetP1 "False", "{point1[0]}", "{point1[1]}", "{point1[2]}"',
            f' .SetP2 "False", "{point2[0]}", "{point2[1]}", "{point2[2]}"',
            ' .LocalCoordinates "False"',
            ' .InvertDirection "False"',
            ' .Radius "0.0"',
            f' .Monitor "{"True" if monitor else "False"}"',
            " .Create",
            "End With",
        ]
        s().add_history(f"discrete port {port_number} ({impedance} ohm)", "\n".join(lines))
        return {"ok": True, "port_number": int(port_number), "type": "discrete",
                "impedance": impedance}

    @registry.tool(
        "cst_list_ports_tool", "List the ports defined in the project and their types.",
        CATEGORY_PORT, params={}, returns="{count, ports}",
        replaces_vba="Port.StartPortNumberIteration / GetNextPortNumber / GetType",
    )
    def list_ports() -> dict[str, Any]:
        s().run_vba(
            "Sub Main\n"
            "Dim n As Long, i As Long, pn As Long, s As String\n"
            "On Error Resume Next\n"
            "n = Port.StartPortNumberIteration()\n"
            "For i = 1 To n\n"
            "pn = Port.GetNextPortNumber()\n"
            's = s & pn & ":" & Port.GetType(pn) & ":" & Port.GetNumberOfModes(pn) & ";"\n'
            "Next i\n"
            'ReportInformationToWindow "MCPPORTS=" & s\n'
            "End Sub\n"
        )
        for m in reversed(s().messages(limit=15)):
            if "MCPPORTS=" in m["text"]:
                body = m["text"].split("MCPPORTS=", 1)[1]
                ports = []
                for chunk in body.split(";"):
                    if not chunk.strip():
                        continue
                    parts = chunk.split(":")
                    ports.append({
                        "port_number": int(parts[0]) if parts[0].isdigit() else parts[0],
                        "type": parts[1] if len(parts) > 1 else "",
                        "modes": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                    })
                return {"ok": True, "count": len(ports), "ports": ports}
        return {"ok": True, "count": 0, "ports": [], "note": "CST did not report any port"}
