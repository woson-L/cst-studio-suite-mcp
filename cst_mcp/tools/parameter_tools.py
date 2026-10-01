"""Design parameter tools.

Parameters are the safe way to drive a CST model. The mechanism used here was
verified on CST 2026.2: `StoreParameters` + `Rebuild` executed as a `Sub Main`
VBA block changes the value and rebuilds the model. Writing the same code into
the history tree is refused by CST (`Prevented attempt to change the value for
parameter ... inside history rebuild`) and, in testing, could leave the Design
Environment unresponsive - so it is never done that way here.
"""
from __future__ import annotations

from typing import Any

from ..registry import ToolRegistry
from ..session import session

CATEGORY = "parameters"


def register_tools(registry: ToolRegistry) -> None:
    s = session

    @registry.tool(
        "cst_get_parameters_tool", "Read every design parameter of the active project (name and value).",
        CATEGORY, params={}, returns="{count, parameters: {name: value}}",
        examples=[{}],
        notes=["Call this before changing anything: CST is the source of truth for names."],
        replaces_vba="GetNumberOfParameters / GetParameterName / RestoreParameter loop",
    )
    def get_parameters() -> dict[str, Any]:
        params = s().list_parameters()
        return {"ok": True, "count": len(params), "parameters": params}

    @registry.tool(
        "cst_set_parameters_tool", "Change one or more design parameters through the CST parameter list.",
        CATEGORY,
        params={"parameters": "dict", "save": "bool"},
        required=["parameters"],
        returns="{changed: {name: value}, method}",
        examples=[{"parameters": {"Lpatch": 26.91, "dinset": 21.6}},
                  {"parameters": {"freq": 2.45}, "save": True}],
        notes=[
            "This is the ONLY correct way to change a parameter.",
            "Never write StoreParameter/StoreParameters/Rebuild into cst_add_to_history_tool.",
            "The model is rebuilt automatically; no separate rebuild call is needed.",
        ],
        replaces_vba="StoreParameters names, values + Rebuild (as a Sub Main block)",
    )
    def set_parameters(parameters: dict[str, Any], save: bool = False) -> dict[str, Any]:
        result = s().set_parameters(parameters)
        if save:
            result["saved"] = s().save_project()
        return result

    @registry.tool(
        "cst_define_parameters_tool",
        "Create or update several parameters at once (the usual first modelling step).",
        CATEGORY,
        params={"parameters": "dict", "save": "bool"},
        required=["parameters"],
        returns="{changed: {name: value}, method}",
        examples=[{"parameters": {"Lg": 60, "Wg": 50, "h": 1.6, "Lpatch": 29.138}}],
        notes=[
            "Runs through the CST parameter list as a Sub Main block - never inside a history block.",
            "Existing parameters keep their value; explicitly different values are then set.",
        ],
        replaces_vba="StoreParameter name, value (repeated)",
    )
    def define_parameters(parameters: dict[str, Any], save: bool = False) -> dict[str, Any]:
        result = s().ensure_parameters(parameters)
        if save:
            result["saved"] = s().save_project()
        return result

    @registry.tool(
        "cst_delete_parameter_tool", "Delete a design parameter from the parameter list.",
        CATEGORY, params={"name": "str"}, required=["name"],
        examples=[{"name": "temp_var"}],
        notes=["Fails if the parameter is still used in the model."],
    )
    def delete_parameter(name: str) -> dict[str, Any]:
        s().run_vba(f'Sub Main\nDeleteParameter "{name}"\nEnd Sub\n')
        return {"ok": True, "deleted": name, "remaining": s().list_parameters()}
