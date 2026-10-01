"""Offline smoke test: import the server, check the registry, print the tool surface.

Does not touch CST, so it can run on a machine without CST installed.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mcp_server  # noqa: E402

registry = mcp_server.registry
print(f"registered tools: {len(registry)}")
print()
grouped = registry.by_category()
for name, specs in sorted(grouped.items()):
    print(f"  {name:12} {len(specs):3}  {', '.join(s.name for s in specs)}")
print()
print("extension discovery:", json.dumps(mcp_server.EXTENSION_REPORT, ensure_ascii=False))
print()
manifest = mcp_server.build_manifest()
print(f"manifest tool_count: {manifest['tool_count']}")
print(f"manifest categories: {[c['name'] for c in manifest['categories']]}")
print(f"workflow steps     : {len(manifest['workflow'])}")

# duplicate-name guard
names = [s.name for s in registry.all()]
dupes = {n for n in names if names.count(n) > 1}
print(f"duplicate tool names: {sorted(dupes) or 'none'}")

out = Path(__file__).resolve().parents[1] / "docs" / "mcp_tools.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes)")
