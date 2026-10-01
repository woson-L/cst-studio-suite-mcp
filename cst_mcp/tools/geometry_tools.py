"""Geometry tools: create and modify solids as named history blocks."""
from __future__ import annotations

from typing import Any, Sequence

from ..registry import ToolRegistry
from ..session import session
from ..vba import geometry as g

CATEGORY = "geometry"

#: Module-level alias for the session factory, un-shadowed so tests (and a swapped
#: session backend) can replace one name. Deliberately not called `s`, because
#: `register_tools` binds a local `s`.
_sess = session


def _rng(values: Sequence[Any] | None, label: str) -> list[Any]:
    if not values or len(values) != 2:
        raise ValueError(f"{label} needs [min, max]")
    return list(values)


def register_tools(registry: ToolRegistry) -> None:
    # Late-bound: resolve `_sess` at call time so replacing the module-level alias
    # is seen by every registered tool instead of being frozen at import time.
    s = lambda *a, **k: _sess(*a, **k)  # noqa: E731

    @registry.tool(
        "cst_create_brick_tool", "Create a rectangular brick (box) as a history block.",
        CATEGORY,
        params={"component": "str", "name": "str", "xrange": "list", "yrange": "list",
                "zrange": "list", "material": "str | null", "title": "str | null"},
        required=["component", "name", "xrange", "yrange", "zrange"],
        returns="{ok, title, solid}",
        examples=[{"component": "board", "name": "substrate",
                   "xrange": ["-Lg/2", "Lg/2"], "yrange": ["-Wg/2", "Wg/2"],
                   "zrange": ["-h", "0"], "material": "FR-4 (lossy)"}],
        notes=["Ranges accept numbers or CST expressions such as \"-Lg/2\"."],
        replaces_vba="Brick object (.Xrange/.Yrange/.Zrange/.Create)",
    )
    def create_brick(component: str, name: str, xrange: list, yrange: list, zrange: list,
                     material: str | None = None, title: str | None = None) -> dict[str, Any]:
        code = g.brick(component, name, _rng(xrange, "xrange"), _rng(yrange, "yrange"),
                       _rng(zrange, "zrange"), material=material)
        return {**s().add_history(title or f"create brick {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_cylinder_tool", "Create a cylinder along x, y or z.",
        CATEGORY,
        params={"component": "str", "name": "str", "axis": "str", "radius": "float",
                "ranges": "list", "center": "list | null", "material": "str | null",
                "segments": "int | null", "title": "str | null"},
        required=["component", "name", "axis", "radius", "ranges"],
        examples=[{"component": "parts", "name": "via", "axis": "z", "radius": 0.3,
                   "ranges": ["0", "1.6"], "material": "Copper (annealed)"}],
        notes=["ranges is the extent along `axis`; center is the centre of the bottom face."],
        replaces_vba="Cylinder object (.OuterRadius/.Xcenter/.Zrange/.Create)",
    )
    def create_cylinder(component: str, name: str, axis: str, radius: Any, ranges: list,
                        center: list | None = None, material: str | None = None,
                        segments: int | None = None, title: str | None = None) -> dict[str, Any]:
        code = g.cylinder(component, name, axis=axis, radius=radius,
                          ranges=_rng(ranges, "ranges"), center=center,
                          material=material, segments=segments)
        return {**s().add_history(title or f"create cylinder {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_sphere_tool", "Create a sphere (optionally truncated by top/bottom radius).",
        CATEGORY,
        params={"component": "str", "name": "str", "center": "list", "radius": "float",
                "top_radius": "float | null", "bottom_radius": "float | null",
                "material": "str | null", "segments": "int | null", "title": "str | null"},
        required=["component", "name", "center", "radius"],
        examples=[{"component": "parts", "name": "ball", "center": [0, 0, 5], "radius": 2}],
        notes=["radius is the equatorial radius (CST CenterRadius)."],
        replaces_vba="Sphere object (.CenterRadius/.Center/.Create)",
    )
    def create_sphere(component: str, name: str, center: list, radius: Any,
                      top_radius: Any | None = None, bottom_radius: Any | None = None,
                      material: str | None = None, segments: int | None = None,
                      title: str | None = None) -> dict[str, Any]:
        code = g.sphere(component, name, center=center, radius=radius,
                        top_radius=top_radius, bottom_radius=bottom_radius,
                        material=material, segments=segments)
        return {**s().add_history(title or f"create sphere {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_cone_tool", "Create a cone or truncated cone.",
        CATEGORY,
        params={"component": "str", "name": "str", "axis": "str", "bottom_radius": "float",
                "top_radius": "float", "ranges": "list", "center": "list | null",
                "material": "str | null", "segments": "int | null", "title": "str | null"},
        required=["component", "name", "axis", "bottom_radius", "top_radius", "ranges"],
        examples=[{"component": "parts", "name": "horn", "axis": "z", "bottom_radius": 1,
                   "top_radius": 4, "ranges": ["0", "10"]}],
        notes=["CST rejects a cone whose top and bottom radii are both zero."],
        replaces_vba="Cone object",
    )
    def create_cone(component: str, name: str, axis: str, bottom_radius: Any, top_radius: Any,
                    ranges: list, center: list | None = None, material: str | None = None,
                    segments: int | None = None, title: str | None = None) -> dict[str, Any]:
        code = g.cone(component, name, axis=axis, bottom_radius=bottom_radius,
                      top_radius=top_radius, ranges=_rng(ranges, "ranges"), center=center,
                      material=material, segments=segments)
        return {**s().add_history(title or f"create cone {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_torus_tool", "Create a torus (ring_radius = ring, tube_radius = tube).",
        CATEGORY,
        params={"component": "str", "name": "str", "center": "list", "ring_radius": "float",
                "tube_radius": "float", "axis": "str", "material": "str | null",
                "segments": "int | null", "title": "str | null"},
        required=["component", "name", "center", "ring_radius", "tube_radius"],
        examples=[{"component": "parts", "name": "loop", "center": [0, 0, 0],
                   "ring_radius": 5, "tube_radius": 1}],
        notes=["CST naming is confusing here: OuterRadius is the ring, InnerRadius the tube."],
        replaces_vba="Torus object (.OuterRadius/.InnerRadius)",
    )
    def create_torus(component: str, name: str, center: list, ring_radius: Any, tube_radius: Any,
                     axis: str = "z", material: str | None = None, segments: int | None = None,
                     title: str | None = None) -> dict[str, Any]:
        code = g.torus(component, name, center=center, ring_radius=ring_radius,
                       tube_radius=tube_radius, axis=axis, material=material, segments=segments)
        return {**s().add_history(title or f"create torus {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_elliptical_cylinder_tool", "Create an elliptical cylinder.",
        CATEGORY,
        params={"component": "str", "name": "str", "axis": "str", "xradius": "float",
                "yradius": "float", "ranges": "list", "center": "list | null",
                "material": "str | null", "segments": "int | null", "title": "str | null"},
        required=["component", "name", "axis", "xradius", "yradius", "ranges"],
        replaces_vba="ECylinder object",
    )
    def create_elliptical_cylinder(component: str, name: str, axis: str, xradius: Any, yradius: Any,
                                   ranges: list, center: list | None = None,
                                   material: str | None = None, segments: int | None = None,
                                   title: str | None = None) -> dict[str, Any]:
        code = g.elliptical_cylinder(component, name, axis=axis, xradius=xradius,
                                     yradius=yradius, ranges=_rng(ranges, "ranges"),
                                     center=center, material=material, segments=segments)
        return {**s().add_history(title or f"create elliptical cylinder {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_create_bondwire_tool", "Create a bond wire between two points.",
        CATEGORY,
        params={"name": "str", "point1": "list", "point2": "list",
                "height": "float", "radius": "float", "material": "str | null",
                "wire_type": "str", "title": "str | null"},
        required=["name", "point1", "point2", "height", "radius"],
        examples=[{"name": "bw1", "point1": [0, 0, 0], "point2": [1, 1, 0],
                   "height": 1, "radius": 0.01}],
        notes=[
            "wire_type: Spline | JEDEC4 | JEDEC5. CST terminates this with .Add.",
            "Wires live in their own tree section: CST's Wire object has no Component.",
            "Non-solid wires accept only PEC or Lossy Metal, and Lossy Metal only with the IE solver.",
        ],
        replaces_vba="Wire object (.Point1/.Height/.Radius/.Add)",
    )
    def create_bondwire(name: str, point1: list, point2: list, height: Any,
                        radius: Any, material: str | None = None, wire_type: str = "Spline",
                        title: str | None = None) -> dict[str, Any]:
        # CST's own error for a bad value is "Invalid bondwire type. Must be:
        # 'Spline', 'JEDEC4' or 'JEDEC5'" (verified live). Validate here so the
        # caller gets that list without a round trip into the model history.
        allowed = ("Spline", "JEDEC4", "JEDEC5")
        hit = next((w for w in allowed if w.lower() == wire_type.strip().lower()), None)
        if hit is None:
            raise ValueError(f"wire_type must be one of {allowed}, got {wire_type!r}")
        code = g.wire(name, point1=point1, point2=point2, height=height,
                      radius=radius, material=material, wire_type=hit)
        return {**s().add_history(title or f"create bondwire {name}", code),
                "wire": name}

    @registry.tool(
        "cst_extrude_curve_tool", "Extrude a closed planar curve item into a solid.",
        CATEGORY,
        params={"component": "str", "name": "str", "curve": "str", "thickness": "float",
                "material": "str | null", "twist": "float | null", "taper": "float | null",
                "title": "str | null"},
        required=["component", "name", "curve", "thickness"],
        notes=["Create the curve first; CST consumes the curve item in this operation."],
        replaces_vba="ExtrudeCurve object",
    )
    def extrude_curve(component: str, name: str, curve: str, thickness: Any,
                      material: str | None = None, twist: Any | None = None,
                      taper: Any | None = None, title: str | None = None) -> dict[str, Any]:
        code = g.extrude_curve(component, name, curve=curve, thickness=thickness,
                               material=material, twist=twist, taper=taper)
        return {**s().add_history(title or f"extrude {curve} -> {component}:{name}", code),
                "solid": g.full_name(component, name)}

    @registry.tool(
        "cst_boolean_tool", "Combine two solids: add (unite), subtract, intersect or insert.",
        CATEGORY,
        params={"operation": "str", "target": "str", "tool": "str", "title": "str | null"},
        required=["operation", "target", "tool"],
        examples=[{"operation": "subtract", "target": "antenna:patch", "tool": "antenna:slot"}],
        notes=[
            "Both names must be full CST names 'component:solid'.",
            "add/subtract/intersect delete the second solid; insert keeps it. The result stays in `target`.",
        ],
        replaces_vba="Solid.Add / Subtract / Intersect / Insert",
    )
    def boolean(operation: str, target: str, tool: str, title: str | None = None) -> dict[str, Any]:
        code = g.boolean(operation, target, tool)
        return {**s().add_history(title or f"{operation} {target} <- {tool}", code),
                "operation": operation, "target": target, "tool": tool}

    @registry.tool(
        "cst_transform_tool", "Transform a solid: translate, rotate, scale or mirror.",
        CATEGORY,
        params={"operation": "str", "name": "str", "vector": "list | null", "center": "list | null",
                "axis": "str", "angle": "float | null", "plane": "str | null",
                "scale": "list | null", "multiple_objects": "bool", "repetitions": "int",
                "group_objects": "bool", "title": "str | null"},
        required=["operation", "name"],
        examples=[{"operation": "translate", "name": "parts:box", "vector": [0, 0, 5]},
                  {"operation": "rotate", "name": "parts:box", "center": [0, 0, 0],
                   "axis": "z", "angle": 90}],
        notes=[
            "translate needs vector; rotate needs center+axis+angle;",
            "scale needs center+scale factors; mirror needs center+plane ('xy'|'xz'|'yz').",
            "CST has no Create on Transform: the block ends with .Transform(\"Shape\", ...).",
        ],
        replaces_vba="Transform.Transform",
    )
    def transform(operation: str, name: str, vector: list | None = None, center: list | None = None,
                  axis: str = "z", angle: Any | None = None, plane: str | None = None,
                  scale: list | None = None, multiple_objects: bool = False,
                  repetitions: int = 1, group_objects: bool = False,
                  title: str | None = None) -> dict[str, Any]:
        # Reject inputs the operation cannot honour, rather than accepting them and
        # emitting a silent no-op or an arbitrary default: a scale without factors
        # used to become a 1,1,1 scale (no change at all) and a mirror without a
        # plane silently used "xy", mirroring the model across a plane the caller
        # never chose.
        op = operation.strip().lower()
        if op == "scale" and (not scale or len(scale) != 3):
            raise ValueError("scale needs three factors, e.g. scale=[2, 2, 2]")
        if op == "mirror" and not plane:
            raise ValueError("mirror needs a plane: 'xy', 'xz' or 'yz'")
        if op == "translate" and center is not None:
            raise ValueError("translate moves by vector only; center is not used for translate")
        code = g.transform_block(operation, name=name, vector=vector, center=center, axis=axis,
                                 angle=angle, plane=plane, scale=scale,
                                 multiple_objects=multiple_objects, repetitions=repetitions,
                                 group_objects=group_objects)
        return {**s().add_history(title or f"{operation} {name}", code), "solid": name}

    @registry.tool(
        "cst_rename_solid_tool", "Rename an existing solid.",
        CATEGORY, params={"old_name": "str", "new_name": "str"}, required=["old_name", "new_name"],
        replaces_vba="Solid.Rename",
    )
    def rename_solid(old_name: str, new_name: str) -> dict[str, Any]:
        return s().add_history(f"rename {old_name} to {new_name}",
                               g.rename_solid(old_name, new_name))

    @registry.tool(
        "cst_delete_solid_tool", "Delete a solid from the model.",
        CATEGORY, params={"name": "str"}, required=["name"],
        replaces_vba="Solid.Delete",
    )
    def delete_solid(name: str) -> dict[str, Any]:
        return s().add_history(f"delete {name}", g.delete_solid(name))

    @registry.tool(
        "cst_move_solid_to_component_tool", "Move a solid into another component.",
        CATEGORY, params={"solid": "str", "component": "str"}, required=["solid", "component"],
        notes=["The target component must already exist (create one with cst_new_component_tool)."],
        replaces_vba="Solid.ChangeComponent",
    )
    def move_solid(solid: str, component: str) -> dict[str, Any]:
        return s().add_history(f"move {solid} to {component}",
                               g.change_component(solid, component))

    @registry.tool(
        "cst_new_component_tool", "Create a new (empty) component in the model tree.",
        CATEGORY, params={"name": "str"}, required=["name"],
        replaces_vba="Component.New",
    )
    def new_component(name: str) -> dict[str, Any]:
        return s().add_history(f"create component {name}", f'Component.New "{name}"')
