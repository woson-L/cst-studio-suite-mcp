# Development scratch script.
#
# Written against one machine and one project, and kept as the record of how the
# findings in tests/evidence/known_failures.md were obtained. It is neither a
# gate nor a documented runner - those are listed in docs/dev/verification.md.
# Point the paths in the configuration block below at your own project first.
#
import inspect
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from mcp.server.fastmcp import FastMCP

print("FastMCP public methods:", [m for m in dir(FastMCP) if not m.startswith("_")])
print()
print("add_tool:", inspect.signature(FastMCP.add_tool))
print("tool    :", inspect.signature(FastMCP.tool))
print("run     :", inspect.signature(FastMCP.run))
