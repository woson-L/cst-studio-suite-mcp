"""Audit the server's self-description: workflow graph, summaries, params, examples.

Static only - never talks to CST. Exits non-zero when a defect is found.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402  (imports registry and bootstraps manifest tools)

problems: list[str] = []
notes: list[str] = []


def problem(msg: str) -> None:
    problems.append(msg)
    print(f"  [FAIL] {msg}")


def ok(msg: str) -> None:
    print(f"  [ ok ] {msg}")


def main() -> int:
    manifest = mcp_server.build_manifest()
    tools = {t["name"]: t for t in manifest["tools"]}
    print(f"registered tools: {len(tools)}")

    # ---------------------------------------------------------------- workflow
    print("\n1. workflow graph")
    wf = manifest["workflow"]
    seen: set[str] = set()
    for step in wf:
        for name in step["tools"]:
            if name not in tools:
                problem(f"workflow step {step['step']} ({step['name']}) names unknown tool {name}")
            seen.add(name)
    ok(f"{len(wf)} steps, {sum(len(s['tools']) for s in wf)} tool references resolved")
    never = sorted(set(tools) - seen)
    notes.append(f"tools not reachable from any workflow step: {len(never)}")

    # steps must be 1..N contiguous and named
    numbers = [s["step"] for s in wf]
    if numbers != list(range(1, len(wf) + 1)):
        problem(f"workflow step numbers are not 1..{len(wf)}: {numbers}")
    for step in wf:
        if not step.get("name") or not step.get("goal"):
            problem(f"workflow step {step['step']} missing name or goal")

    # ---------------------------------------------------------------- summaries
    print("\n2. tool descriptions")
    for name, t in tools.items():
        summary = (t.get("summary") or "").strip()
        if not summary:
            problem(f"{name}: empty summary")
        elif len(summary) < 15:
            problem(f"{name}: summary too short to be useful ({summary!r})")
        if not summary[:1].isupper():
            problem(f"{name}: summary does not start with a capital letter ({summary[:40]!r})")
        if t.get("category") not in {
            "export", "geometry", "material", "mesh", "meta", "monitor",
            "parameters", "port", "results", "runtime", "session", "solver", "sweep", "verify",
        }:
            problem(f"{name}: unexpected category {t.get('category')!r}")

    # naming convention cst_<verb>_<object>_tool
    for name in tools:
        if not re.fullmatch(r"cst_[a-z0-9_]+_tool", name):
            problem(f"{name}: violates naming convention cst_<verb>_<object>_tool")
    ok(f"{len(tools)} summaries and names checked")

    # ---------------------------------------------------------------- examples
    print("\n3. examples and parameter tables")
    for name, t in tools.items():
        params = t.get("params") or {}
        required = t.get("required") or []
        for key in required:
            if key not in params:
                problem(f"{name}: required key {key!r} is not declared in params")
        for ex in t.get("examples") or []:
            if not isinstance(ex, dict):
                problem(f"{name}: example is not an object: {ex!r}")
                continue
            extra = sorted(set(ex) - set(params))
            if extra:
                problem(f"{name}: example passes undeclared key(s) {extra}")
            missing = sorted(set(required) - set(ex))
            if missing:
                problem(f"{name}: example omits required key(s) {missing}")

    # ---------------------------------------------------------------- manifest
    print("\n4. manifest consistency")
    on_disk = ROOT / "docs" / "mcp_tools.json"
    if not on_disk.is_file():
        problem("docs/mcp_tools.json is missing")
    else:
        saved = json.loads(on_disk.read_text(encoding="utf-8"))
        if saved.get("tool_count") != len(tools):
            problem(
                f"docs/mcp_tools.json is stale: says {saved.get('tool_count')} "
                f"tools, live registry has {len(tools)}"
            )
        saved_names = {t["name"] for t in saved.get("tools", [])}
        if saved_names != set(tools):
            problem(f"docs/mcp_tools.json tool set differs from the registry "
                    f"(only in manifest: {sorted(saved_names - set(tools))}, "
                    f"only in registry: {sorted(set(tools) - saved_names)})")
        else:
            ok("docs/mcp_tools.json matches the live registry")

    # declared count in prose must match reality
    for doc in (ROOT / "README.md", ROOT / "docs" / "start" / "install.md",
                ROOT / "docs" / "use" / "quickstart.md",
                ROOT / "skills" / "cst-studio-suite-mcp" / "SKILL.md"):
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        for match in re.finditer(r"\b(\d{2,3})\s*(?:tools|个工具)\b", text):
            claimed = int(match.group(1))
            if claimed != len(tools):
                problem(f"{doc.name}: claims {claimed} tools, registry has {len(tools)}")

    # ------------------------------------------------------------------ report
    print("\n5. summary")
    for note in notes:
        print(f"  [info] {note}")
    print(f"\nproblems found: {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
