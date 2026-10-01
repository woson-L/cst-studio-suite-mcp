"""Extensible tool registry for the CST MCP.

Why a registry instead of a long list of `@mcp.tool()` functions
---------------------------------------------------------------
Every tool is described once, in data, and then:

* registered with FastMCP,
* serialised into the machine-readable manifest (docs/mcp_tools.json) that other
  agents read,
* used to generate the human-readable tool reference,
* extended by dropping a new module into `cst_mcp/tools/` (see registry.
  discover_extensions()).

Adding a tool therefore never means editing the server plumbing - which is what
makes it practical to keep growing the surface later.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

# --------------------------------------------------------------------------- spec
@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool, described as data."""

    name: str
    summary: str
    category: str
    handler: Callable[..., Any]
    params: dict[str, str] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    returns: str = ""
    examples: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()
    replaces_vba: str = ""
    extension: bool = False

    def json_schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        for key, hint in self.params.items():
            properties[key] = _hint_to_schema(hint)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if self.required:
            schema["required"] = list(self.required)
        return schema

    def to_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "summary": self.summary,
            "params": self.params,
            "required": list(self.required),
            "json_schema": self.json_schema(),
            "returns": self.returns,
            "examples": list(self.examples),
            "notes": list(self.notes),
            "replaces_vba": self.replaces_vba,
            "extension": self.extension,
        }


def _hint_to_schema(hint: str) -> dict[str, Any]:
    """Turn a short hint like 'int', 'str', 'str | null' into a JSON schema fragment."""
    text = (hint or "str").strip()
    optional = "null" in text or "optional" in text.lower()
    base = text.split("|")[0].strip().lower()
    mapping = {
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "number": {"type": "number"},
        "bool": {"type": "boolean"},
        "dict": {"type": "object"},
        "obj": {"type": "object"},
        "list": {"type": "array"},
        "array": {"type": "array"},
        "str": {"type": "string"},
        "any": {},
    }
    schema = dict(mapping.get(base, {"type": "string"}))
    if optional and schema:
        schema["type"] = [schema["type"], "null"]
    return schema


# --------------------------------------------------------------------------- registry
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    # -- registration ------------------------------------------------------
    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} is already registered")
        if not spec.name.startswith("cst_"):
            raise ValueError(f"tool name {spec.name!r} must start with 'cst_'")
        self._tools[spec.name] = spec
        return spec

    def add(
        self,
        name: str,
        summary: str,
        category: str,
        handler: Callable[..., Any],
        *,
        params: dict[str, str] | None = None,
        required: Iterable[str] = (),
        returns: str = "",
        examples: Iterable[dict[str, Any]] = (),
        notes: Iterable[str] = (),
        replaces_vba: str = "",
        extension: bool = False,
    ) -> ToolSpec:
        return self.register(
            ToolSpec(
                name=name,
                summary=summary,
                category=category,
                handler=handler,
                params=dict(params or {}),
                required=tuple(required),
                returns=returns,
                examples=tuple(examples),
                notes=tuple(notes),
                replaces_vba=replaces_vba,
                extension=extension,
            )
        )

    def tool(
        self,
        name: str,
        summary: str,
        category: str,
        *,
        params: dict[str, str] | None = None,
        required: Iterable[str] = (),
        returns: str = "",
        examples: Iterable[dict[str, Any]] = (),
        notes: Iterable[str] = (),
        replaces_vba: str = "",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form: @registry.tool('cst_x', 'summary', 'category')."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add(
                name, summary, category, fn,
                params=params, required=required, returns=returns,
                examples=examples, notes=notes, replaces_vba=replaces_vba,
            )
            return fn

        return decorator

    # -- lookup ------------------------------------------------------------
    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"unknown tool {name!r}. Available: {', '.join(sorted(self._tools))}"
            ) from None

    def all(self) -> list[ToolSpec]:
        return [self._tools[k] for k in sorted(self._tools)]

    def by_category(self) -> dict[str, list[ToolSpec]]:
        grouped: dict[str, list[ToolSpec]] = {}
        for spec in self.all():
            grouped.setdefault(spec.category, []).append(spec)
        return grouped

    def names(self) -> list[str]:
        return sorted(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    # -- extensibility -----------------------------------------------------
    def discover_extensions(self, package: str = "cst_mcp.tools") -> dict[str, Any]:
        """Import every module in `package` so it can register its own tools.

        A new capability is added by dropping a module into cst_mcp/tools/ that
        calls `register_tools(registry)`. Nothing else has to change, which is
        what keeps the surface growable.
        """
        report: dict[str, Any] = {"package": package, "loaded": [], "failed": []}
        try:
            pkg = importlib.import_module(package)
        except Exception as exc:  # noqa: BLE001
            report["failed"].append({"module": package, "error": f"{type(exc).__name__}: {exc}"})
            return report

        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_"):
                continue
            full = f"{package}.{info.name}"
            try:
                module = importlib.import_module(full)
            except Exception as exc:  # noqa: BLE001
                report["failed"].append({"module": full, "error": f"{type(exc).__name__}: {exc}"})
                continue
            hook = getattr(module, "register_tools", None)
            if callable(hook):
                try:
                    before = len(self)
                    hook(self)
                    report["loaded"].append({"module": full, "tools_added": len(self) - before})
                except Exception as exc:  # noqa: BLE001
                    report["failed"].append({"module": full, "error": f"{type(exc).__name__}: {exc}"})
            else:
                report["loaded"].append({"module": full, "tools_added": 0, "note": "no register_tools() hook"})
        return report


def describe_handler(fn: Callable[..., Any]) -> str:
    """Return a compact signature string for documentation."""
    try:
        return str(inspect.signature(fn))
    except (TypeError, ValueError):
        return "(...)"
