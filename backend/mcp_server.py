"""MCP server exposing Neighbour Node's geo-search and trust-check tools, plus a
listing lookup resource, to any MCP client (Claude Code, Cursor, a custom client).

The tools are thin adapters. The logic lives in the service layer and is called
in-process by the match agent as well — one implementation, two callers, one
TraceLog. Nothing here reimplements haversine or the trust rules.

Run directly (`python mcp_server.py`), not through manage.py: this is a stdio
server, not a Django management command.

IMPORTANT: stdout is the JSON-RPC transport. A single print() corrupts the
stream and the client drops the server with no error shown. All diagnostics go
to stderr.
"""

import os
import sys
from pathlib import Path

# Django has to be configured before any model import. mcp_server.py sits next to
# manage.py, so its own directory is the import root for `config` and `apps`.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.listings.models import Listing  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

mcp = MCPServer("neighbour-node")


@mcp.tool()
def ping() -> str:
    """Smoke test: confirm the server is up and can reach the database."""
    return f"neighbour-node MCP server up. {Listing.objects.count()} listings."


if __name__ == "__main__":
    print("neighbour-node MCP server starting on stdio", file=sys.stderr)
    mcp.run(transport="stdio")
