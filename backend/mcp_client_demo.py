"""A minimal MCP client that drives the neighbour-node server over stdio.

Exists to make the MCP integration demonstrable and repeatable: it spawns
mcp_server.py as a subprocess, completes the handshake, DISCOVERS the tools and
resources rather than assuming them, and then calls two of them. Nothing here
imports Django or the service layer — it only speaks the protocol, which is the
point. If this script works, any MCP client works.

Run one step at a time so each screen is a single legible screenshot:

    python mcp_client_demo.py connect
    python mcp_client_demo.py discover
    python mcp_client_demo.py geo
    python mcp_client_demo.py trust
    python mcp_client_demo.py all      # default

The demo inputs are fixed (see DEMO_LAT / DEMO_LNG / DEMO_RADIUS_KM) and chosen
against the seeded data so the output stays small enough to read on a slide.
`trust` resolves its listing id from the geo_search results instead of hardcoding
a primary key, so a reseeded database doesn't break the demo.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BACKEND_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = BACKEND_DIR / "mcp_server.py"

# Reference point the seed data is built around (~Philadelphia). At 3.5 km this
# returns three listings — enough to show ranking by distance, few enough to fit
# on one screen. Widening to 5 km pulls in six and the shot stops being readable.
DEMO_LAT = 40.0
DEMO_LNG = -75.0
DEMO_RADIUS_KM = 3.5

# The seeded listing that breaks exactly one trust rule: a claw hammer priced at
# $1,450, which is far outside the plausible band for tools. One flag, one
# sentence to explain it.
DEMO_TRUST_TITLE = "Claw Hammer"

# Headings are numbered from 2 on purpose: they line up with the screenshot
# numbering in docs/mcp.md, where shot 1 is the server booting on its own. Each
# captured frame then says which shot it is.
RULE = "─" * 64


def heading(text):
    print(f"\n{RULE}\n  {text}\n{RULE}")


def dump(payload):
    """Print a result as indented JSON — the shape a client actually receives."""
    print(json.dumps(payload, indent=2, default=str))


def tool_payload(result):
    """Pull the JSON body out of a CallToolResult.

    Servers may return a parsed structured result, unstructured text content, or
    both. Prefer the structured form and fall back to parsing the text block, so
    the demo doesn't depend on which one this server happens to send.
    """
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        if getattr(block, "type", None) == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return {"text": block.text}
    return {}


async def step_connect(session, quiet=False):
    """Handshake. Proves the transport works before any tool is called."""
    info = await session.initialize()
    if quiet:
        return info
    heading("2. CONNECTED — initialize handshake over stdio")
    print(f"  server      : {info.server_info.name} v{info.server_info.version}")
    print(f"  protocol    : {info.protocol_version}")
    capabilities = [
        name
        for name in ("tools", "resources", "prompts")
        if getattr(info.capabilities, name, None) is not None
    ]
    print(f"  capabilities: {', '.join(capabilities)}")
    return info


async def step_discover(session):
    """List what the server offers. This is discovery, not a hardcoded call —
    the names below came off the wire."""
    tools = await session.list_tools()
    templates = await session.list_resource_templates()

    heading("3. DISCOVERED — tools/list and resources/templates/list")
    print(f"\n  TOOLS ({len(tools.tools)})\n")
    for tool in tools.tools:
        summary = (tool.description or "").strip().splitlines()[0]
        required = tool.input_schema.get("required", [])
        params = ", ".join(tool.input_schema.get("properties", {}))
        print(f"  • {tool.name}")
        print(f"      {summary}")
        print(f"      params  : {params}")
        print(f"      required: {', '.join(required) or '(none)'}")
    print(f"\n  RESOURCES ({len(templates.resource_templates)})\n")
    for template in templates.resource_templates:
        summary = (template.description or "").strip().splitlines()[0]
        print(f"  • {template.uri_template}")
        print(f"      {summary}")
    return tools


async def step_geo(session, quiet=False):
    """Call geo_search with the fixed demo point."""
    arguments = {
        "lat": DEMO_LAT,
        "lng": DEMO_LNG,
        "radius_km": DEMO_RADIUS_KM,
    }
    result = await session.call_tool("geo_search", arguments)
    payload = tool_payload(result)
    if quiet:
        return payload

    heading("4. CALLED geo_search — items near a point, nearest first")
    print(f"\n  arguments: {json.dumps(arguments)}\n")
    dump(payload)
    return payload


async def step_trust(session, listing_id):
    """Call trust_check on one listing id taken from the geo_search results."""
    arguments = {"listing_id": listing_id}
    result = await session.call_tool("trust_check", arguments)
    payload = tool_payload(result)

    heading("5. CALLED trust_check — consistency rules for one listing")
    print(f"\n  arguments: {json.dumps(arguments)}\n")
    dump(payload)

    flags = payload.get("flags", [])
    print(f"\n  → {len(flags)} flag(s):")
    for flag in flags:
        print(f"      [{flag['severity']}] {flag['code']}: {flag['message']}")
    return payload


def resolve_listing_id(geo_payload):
    """Find the demo listing in the geo_search results.

    Matching on title rather than a hardcoded id keeps the demo working after a
    reseed, when primary keys shift.
    """
    for listing in geo_payload.get("listings", []):
        if DEMO_TRUST_TITLE.lower() in listing["title"].lower():
            return listing["id"]
    raise SystemExit(
        f"No listing matching {DEMO_TRUST_TITLE!r} within {DEMO_RADIUS_KM} km of "
        f"({DEMO_LAT}, {DEMO_LNG}).\n"
        "Seed the database first:  python manage.py seed_data --clear"
    )


async def main(step):
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(BACKEND_DIR),
    )
    # errlog=DEVNULL would hide the server's stderr banner; keep it visible so a
    # server that fails to boot says so instead of looking like a client bug.
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await step_connect(session, quiet=step != "connect" and step != "all")

            if step in ("discover", "all"):
                await step_discover(session)

            if step in ("geo", "all"):
                geo = await step_geo(session)
            elif step == "trust":
                geo = await step_geo(session, quiet=True)

            if step in ("trust", "all"):
                await step_trust(session, resolve_listing_id(geo))

    print()


if __name__ == "__main__":
    STEPS = ("connect", "discover", "geo", "trust", "all")
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    if requested not in STEPS:
        raise SystemExit(f"Usage: python mcp_client_demo.py [{'|'.join(STEPS)}]")
    asyncio.run(main(requested))
