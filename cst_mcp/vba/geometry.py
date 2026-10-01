"""Geometry builders: structured arguments -> CST VBA history blocks.

Every method name here was taken from the CST Studio Suite 2026 VBA reference
(Online Help -> VBA_3D) and, where possible, exercised against a live CST 2026.2.

Naming traps that this module handles for the caller:

* the elliptical cylinder object is spelled ``ECylinder``, and uses lowercase-r
  ``Xradius``/``Yradius``
* ``Cylinder`` takes ``OuterRadius``/``InnerRadius`` and three separate
  ``Xcenter``/``Ycenter``/``Zcenter`` calls - not ``Radius``/``Center``
* ``Sphere`` takes ``CenterRadius`` (equatorial radius) plus ``TopRadius`` and
  ``BottomRadius``, and ``Center(x, y, z)`` as three separate arguments
* ``Torus``'s ``OuterRadius`` is the *ring* radius and ``InnerRadius`` is the
  *tube* radius - the opposite reading from Cylinder
* ``Transform`` has no ``Create``: it ends with ``.Transform("Shape","<how>")``
* ``Wire`` ends with ``.Add``, not ``.Create``

Conventions
-----------
* Solid names are full CST names ``component:solid``; a bare name is completed
  with the component being created.
* Coordinate arguments may be numbers or CST parameter expressions such as
  ``"-Lg/2"``; they are always emitted quoted so expressions survive.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

__all__ = [
    "full_name",
    "coord",
    "brick",
    "cylinder",
    "sphere",
    "cone",
    "torus",
    "elliptical_cylinder",
    "wire",
    "extrude_curve",
    "boolean",
    "transform_block",
    "rename_solid",
    "delete_solid",
    "change_material",
    "change_component",
]

AXES = ("x", "y", "z")


def full_name(component: str, solid: str) -> str:
    return solid if ":" in solid else f"{component}:{solid}"


def coord(value: Any) -> str:
    """Render one coordinate value as a quoted CST expression."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _q(value: Any) -> str:
    return f'"{coord(value)}"'


def _range(keyword: str, values: Sequence[Any]) -> str:
    if len(values) != 2:
        raise ValueError(f"{keyword} needs exactly two values, got {values!r}")
    return f" .{keyword} {_q(values[0])}, {_q(values[1])}"


def _head(obj: str, component: str, name: str, material: str | None) -> list[str]:
    lines = [f"With {obj}", " .Reset", f' .Name "{name}"', f' .Component "{component}"']
    if material:
        lines.append(f' .Material "{material}"')
    return lines


def _finish(lines: Iterable[str], terminator: str = " .Create") -> str:
    return "\n".join([*lines, terminator, "End With"]) + "\n"


def _axis(value: str) -> str:
    key = str(value).strip().lower()
    if key not in AXES:
        raise ValueError("axis must be x, y or z")
    return key


def _point3(values: Sequence[Any], label: str) -> list[Any]:
    if len(values) != 3:
        raise ValueError(f"{label} needs [x, y, z]")
    return list(values)


def _centre_lines(obj_lines: list[str], center: Sequence[Any]) -> None:
    x, y, z = _point3(center, "center")
    obj_lines.append(f" .Xcenter {_q(x)}")
    obj_lines.append(f" .Ycenter {_q(y)}")
    obj_lines.append(f" .Zcenter {_q(z)}")


# --------------------------------------------------------------------- solids
def brick(component: str, name: str, xrange: Sequence[Any], yrange: Sequence[Any],
          zrange: Sequence[Any], *, material: str | None = None) -> str:
    lines = _head("Brick", component, name, material)
    lines += [_range("Xrange", xrange), _range("Yrange", yrange), _range("Zrange", zrange)]
    return _finish(lines)


def cylinder(component: str, name: str, *, axis: str, radius: Any,
             ranges: Sequence[Any], material: str | None = None,
             segments: int | None = None, center: Sequence[Any] | None = None,
             inner_radius: Any | None = None) -> str:
    ax = _axis(axis)
    lines = _head("Cylinder", component, name, material)
    lines.append(f' .Axis "{ax}"')
    lines.append(f" .OuterRadius {_q(radius)}")
    lines.append(f" .InnerRadius {_q(inner_radius if inner_radius is not None else 0)}")
    if center:
        _centre_lines(lines, center)
    lines.append(_range(f"{ax.upper()}range", ranges))
    if segments is not None:
        lines.append(f" .Segments {int(segments)}")
    return _finish(lines)


def sphere(component: str, name: str, *, center: Sequence[Any], radius: Any,
           material: str | None = None, segments: int | None = None,
           axis: str = "z", top_radius: Any | None = None,
           bottom_radius: Any | None = None) -> str:
    lines = _head("Sphere", component, name, material)
    lines.append(f' .Axis "{_axis(axis)}"')
    lines.append(f" .CenterRadius {_q(radius)}")
    lines.append(f" .TopRadius {_q(top_radius if top_radius is not None else 0)}")
    lines.append(f" .BottomRadius {_q(bottom_radius if bottom_radius is not None else 0)}")
    x, y, z = _point3(center, "center")
    lines.append(f" .Center {_q(x)}, {_q(y)}, {_q(z)}")
    if segments is not None:
        lines.append(f" .Segments {int(segments)}")
    return _finish(lines)


def cone(component: str, name: str, *, axis: str, bottom_radius: Any, top_radius: Any,
         ranges: Sequence[Any], material: str | None = None, segments: int | None = None,
         center: Sequence[Any] | None = None) -> str:
    if float(_numeric(bottom_radius)) == 0.0 and float(_numeric(top_radius)) == 0.0:
        raise ValueError("CST rejects a cone whose top and bottom radii are both zero")
    ax = _axis(axis)
    lines = _head("Cone", component, name, material)
    lines.append(f' .Axis "{ax}"')
    lines.append(f" .TopRadius {_q(top_radius)}")
    lines.append(f" .BottomRadius {_q(bottom_radius)}")
    if center:
        _centre_lines(lines, center)
    lines.append(_range(f"{ax.upper()}range", ranges))
    if segments is not None:
        lines.append(f" .Segments {int(segments)}")
    return _finish(lines)


def torus(component: str, name: str, *, center: Sequence[Any], ring_radius: Any,
          tube_radius: Any, axis: str = "z", material: str | None = None,
          segments: int | None = None) -> str:
    """CST's OuterRadius is the ring radius, InnerRadius is the tube radius."""
    lines = _head("Torus", component, name, material)
    lines.append(f' .Axis "{_axis(axis)}"')
    lines.append(f" .OuterRadius {_q(ring_radius)}")
    lines.append(f" .InnerRadius {_q(tube_radius)}")
    _centre_lines(lines, center)
    if segments is not None:
        lines.append(f" .Segments {int(segments)}")
    return _finish(lines)


def elliptical_cylinder(component: str, name: str, *, axis: str, xradius: Any, yradius: Any,
                        ranges: Sequence[Any], material: str | None = None,
                        segments: int | None = None,
                        center: Sequence[Any] | None = None) -> str:
    ax = _axis(axis)
    lines = _head("ECylinder", component, name, material)
    lines.append(f' .Axis "{ax}"')
    lines.append(f" .Xradius {_q(xradius)}")
    lines.append(f" .Yradius {_q(yradius)}")
    if center:
        _centre_lines(lines, center)
    lines.append(_range(f"{ax.upper()}range", ranges))
    if segments is not None:
        lines.append(f" .Segments {int(segments)}")
    return _finish(lines)


def wire(name: str, *, point1: Sequence[Any], point2: Sequence[Any],
         height: Any, radius: Any, material: str | None = None,
         wire_type: str = "Spline", termination: str = "natural") -> str:
    """A bond wire.

    CST's Wire object lives in its own tree section and has no `.Component`
    method - passing one fails with "no such property or method". The block
    terminates with `.Add`, not `.Create`.
    """
    p1 = _point3(point1, "point1")
    p2 = _point3(point2, "point2")
    lines = ["With Wire", " .Reset", f' .Name "{name}"',
             ' .Type ("Bondwire")',
             f' .BondWireType ("{wire_type}")']
    lines.append(f" .Point1 {_q(p1[0])}, {_q(p1[1])}, {_q(p1[2])}, False")
    lines.append(f" .Point2 {_q(p2[0])}, {_q(p2[1])}, {_q(p2[2])}, False")
    lines.append(f" .Height {_q(height)}")
    lines.append(f" .Radius {_q(radius)}")
    lines.append(f' .Termination ("{termination}")')
    if material:
        lines.append(f' .Material "{material}"')
    return _finish(lines, " .Add")


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def extrude_curve(component: str, name: str, *, curve: str, thickness: Any,
                  material: str | None = None, twist: Any | None = None,
                  taper: Any | None = None) -> str:
    """Extrude a closed planar curve item into a solid (the curve item is consumed)."""
    lines = _head("ExtrudeCurve", component, name, material)
    lines.append(f" .Thickness {_q(thickness)}")
    lines.append(f" .Twistangle {_q(twist if twist is not None else 0)}")
    lines.append(f" .Taperangle {_q(taper if taper is not None else 0)}")
    lines.append(f' .Curve "{curve}"')
    return _finish(lines)


# ------------------------------------------------------------------- booleans
_BOOLEAN = {
    "add": "Solid.Add",
    "unite": "Solid.Add",
    "subtract": "Solid.Subtract",
    "insert": "Solid.Insert",
    "intersect": "Solid.Intersect",
}


def boolean(operation: str, target: str, tool: str) -> str:
    key = operation.strip().lower()
    if key not in _BOOLEAN:
        raise ValueError(f"operation must be one of {sorted(_BOOLEAN)}")
    if ":" not in target or ":" not in tool:
        raise ValueError("target and tool must be full CST names such as 'component:solid'")
    return f'{_BOOLEAN[key]} "{target}", "{tool}"\n'


# ----------------------------------------------------------------- transforms
def transform_block(operation: str, *, name: str, vector: Sequence[Any] | None = None,
                    center: Sequence[Any] | None = None, axis: str = "z",
                    angle: Any | None = None, plane: str | None = None,
                    scale: Sequence[Any] | None = None,
                    multiple_objects: bool = False, repetitions: int = 1,
                    group_objects: bool = False) -> str:
    """One Solid > Transform history block.

    Verified against the 2026 reference:
      Translate -> .Vector(x,y,z) + .Center(x,y,z) + .Transform("Shape","Translate")
      Rotate    -> .Origin("Free") + .Center(x,y,z) + .Angle(x,y,z) + .Transform("Shape","Rotate")
      Scale     -> .Origin("Free") + .Center(x,y,z) + .ScaleFactor(x,y,z) + .Transform("Shape","Scale")
      Mirror    -> .Origin("Free") + .Center(x,y,z) + .PlaneNormal(x,y,z) + .Transform("Shape","Mirror")
    There is no .Create on this object.
    """
    key = operation.strip().lower()
    if key not in {"translate", "rotate", "scale", "mirror"}:
        raise ValueError("operation must be translate, rotate, scale or mirror")

    lines = ["With Transform", " .Reset", f' .Name "{name}"']
    if key == "translate":
        if not vector or len(vector) != 3:
            raise ValueError("translate needs vector [dx, dy, dz]")
        lines.append(" .Origin \"Free\"")
        lines.append(f' .Vector {_q(vector[0])}, {_q(vector[1])}, {_q(vector[2])}')
    else:
        if not center or len(center) != 3:
            raise ValueError(f"{key} needs center [x, y, z]")
        lines.append(" .Origin \"Free\"")
        lines.append(f' .Center {_q(center[0])}, {_q(center[1])}, {_q(center[2])}')
        if key == "rotate":
            if angle is None:
                raise ValueError("rotate needs angle in degrees")
            ax = _axis(axis)
            triple = [0, 0, 0]
            triple[AXES.index(ax)] = angle
            lines.append(f' .Angle {_q(triple[0])}, {_q(triple[1])}, {_q(triple[2])}')
        elif key == "scale":
            factors = list(scale) if scale else [1, 1, 1]
            if len(factors) != 3:
                raise ValueError("scale needs three factors")
            lines.append(f' .ScaleFactor {_q(factors[0])}, {_q(factors[1])}, {_q(factors[2])}')
        else:  # mirror
            plane_key = (plane or "xy").strip().lower()
            if plane_key not in {"xy", "xz", "yz"}:
                raise ValueError("mirror needs plane xy, xz or yz")
            normal = {"xy": [0, 0, 1], "xz": [0, 1, 0], "yz": [1, 0, 0]}[plane_key]
            lines.append(f' .PlaneNormal {_q(normal[0])}, {_q(normal[1])}, {_q(normal[2])}')

    lines.append(f' .MultipleObjects "{"True" if multiple_objects else "False"}"')
    if group_objects:
        lines.append(' .GroupObjects "True"')
    lines.append(f" .Repetitions {int(repetitions)}")
    lines.append(f' .Transform ("Shape", "{key.capitalize()}")')
    lines.append("End With")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- solid edits
def rename_solid(old_name: str, new_name: str) -> str:
    return f'Solid.Rename "{old_name}", "{new_name}"\n'


def delete_solid(name: str) -> str:
    return f'Solid.Delete "{name}"\n'


def change_material(solid: str, material: str) -> str:
    return f'Solid.ChangeMaterial "{solid}", "{material}"\n'


def change_component(solid: str, component: str) -> str:
    return f'Solid.ChangeComponent "{solid}", "{component}"\n'
