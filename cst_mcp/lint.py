"""Guards that keep a generated macro from breaking or blocking CST.

Two CST 2026 behaviours make this necessary:

1. A parameter change inside a history rebuild is refused:
       "Prevented attempt to change the value for parameter X inside history
        rebuild at step N."
2. A `Rebuild` inside a structure macro is refused:
       "(&H8000FFFF) The rebuild operation cannot be used inside a structure
        macro."
   In testing, submitting that block through `add_to_history` left the Design
   Environment permanently unresponsive - every later call hung.

So a history block is linted before it ever reaches CST, and the error explains
what to do instead. A lint that returns a clear message is far cheaper than a
hung CST session.
"""
from __future__ import annotations

import re
from typing import Any

__all__ = [
    "HistoryBlockRejected",
    "ParameterValueRejected",
    "lint_history_block",
    "validate_parameter_values",
    "PARAMETER_TOOLS",
]


class HistoryBlockRejected(ValueError):
    """A history block would be refused by CST or would block the session."""


class ParameterValueRejected(ValueError):
    """A parameter value cannot be sent to CST as-is."""


#: CST parameter names are plain identifiers. Enforcing this also closes a VBA
#: injection path, because the name is interpolated into the StoreParameters block.
_PARAMETER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


# token -> (what to use instead)
_FORBIDDEN_IN_HISTORY: dict[str, str] = {
    "storeparameters": "use cst_set_parameters_tool (parameter list)",
    "storeparameterwithdescription": "use cst_set_parameters_tool",
    "storeparameter": "use cst_set_parameters_tool; a parameter value must not be written in a history block",
    "storedoubleparameter": "use cst_set_parameters_tool",
    "restoreparameter": "read parameters with cst_get_parameters_tool",
    "restoredoubleparameter": "read parameters with cst_get_parameters_tool",
    "rebuildonparametricchange": "not allowed inside a history block",
    "makesureparameterexists": "define the parameter once in the parameter block, then use cst_set_parameters_tool",
    "deleteparameter": "manage parameters with cst_set_parameters_tool",
    "renameparameter": "manage parameters with cst_set_parameters_tool",
}

# A bare `Rebuild` statement is the form that triggers the structure-macro error.
_REBUILD_STATEMENT = re.compile(r"(?<![\w.])rebuild\s*$", re.IGNORECASE | re.MULTILINE)

# Tools whose names the linter may suggest.
PARAMETER_TOOLS = ("cst_set_parameters_tool", "cst_get_parameters_tool")


def _strip_vba_comments(code: str) -> str:
    """Drop `' comment` and `REM ...` tails so commented code does not trip the lint."""
    out = []
    for line in code.splitlines():
        no_quote = line.split("'", 1)[0]
        if re.match(r"\s*rem\b", no_quote, re.IGNORECASE):
            continue
        out.append(no_quote)
    return "\n".join(out)


def lint_history_block(title: str, code: str) -> None:
    """Raise HistoryBlockRejected if this block must not be handed to CST."""
    body = _strip_vba_comments(code)
    lowered = body.lower()

    for token, advice in _FORBIDDEN_IN_HISTORY.items():
        if token in lowered:
            raise HistoryBlockRejected(
                f"history block {title!r} contains {token!r}. CST 2026 refuses this "
                f"('Prevented attempt to change the value for parameter ... inside history "
                f"rebuild' / 'The rebuild operation cannot be used inside a structure macro.') "
                f"and can leave the Design Environment blocked. Action: {advice}."
            )

    if _REBUILD_STATEMENT.search(body):
        raise HistoryBlockRejected(
            f"history block {title!r} calls Rebuild. CST 2026 refuses that inside a history "
            f"structure macro and can block the Design Environment. Action: remove Rebuild - "
            f"the model is rebuilt automatically after the block; to change a parameter use "
            f"cst_set_parameters_tool."
        )


def validate_parameter_values(parameters: dict[str, Any]) -> dict[str, str]:
    """Normalise and sanity-check a parameter update."""
    if not parameters:
        raise ParameterValueRejected("parameters must not be empty")
    pairs: dict[str, str] = {}
    for raw_name, raw_value in parameters.items():
        name = str(raw_name).strip()
        if not name:
            raise ParameterValueRejected("parameter name must not be empty")
        # The name is interpolated into the `n(i) = "<name>"` array of the
        # StoreParameters block, so a quote or separator in it is an injection
        # point into VBA - the same reason values are checked below. A name such as
        # 'Lg": Rebuild: x="' used to pass and emit
        #     n(1) = "Lg": Rebuild: x=""
        # which is a second VBA statement, not a parameter name.
        if not _PARAMETER_NAME_RE.match(name):
            raise ParameterValueRejected(
                f"parameter name {name!r} is not a valid identifier. CST parameter names "
                "must start with a letter or underscore and contain only letters, digits "
                "and underscores."
            )
        if raw_value is None:
            raise ParameterValueRejected(f"parameter {name!r} needs a value")
        value = str(raw_value).strip()
        if not value:
            raise ParameterValueRejected(f"parameter {name!r} needs a non-empty value")
        # A comma almost always means a list was passed where a single expression
        # is expected. Report it instead of sending a broken expression to CST.
        if "," in value and not (value.startswith("(") and value.endswith(")")):
            raise ParameterValueRejected(
                f"parameter {name!r} value {value!r} looks like a list. "
                "Pass one value per parameter (CST expects a single numeric expression)."
            )
        if '"' in value:
            raise ParameterValueRejected(
                f"parameter {name!r} value {value!r} contains a quote character."
            )
        pairs[name] = value
    return pairs
