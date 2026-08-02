"""The MCP server, exercised through the protocol.

Not by calling geo_search() and trust_check() as plain functions — those are
thin adapters over `matching.services` and `matching.trust`, both already
covered, and testing them directly would prove nothing the existing suite
doesn't. What is untested is everything BETWEEN a client and that logic: the
tool registration, the JSON schema the decorator derives from the signature,
the argument validation, and the shape of what comes back over the wire.

Uses the library's in-memory transport (`Client(mcp)`) rather than spawning
mcp_server.py as a subprocess. Same protocol layer, same dispatch, no process
to leak if an assertion fails mid-test.

TransactionTestCase, not TestCase: sync tools are dispatched on worker threads,
and TestCase wraps each test in a transaction that other threads' connections
cannot see — fixtures would be invisible to the tool and every search would
return nothing.
"""

import asyncio
import json

from apps.core.testing import make_listing, make_user
from django.test import TransactionTestCase
from mcp.client import Client

# Imported for its side effects as well as its symbols: the module configures
# Django and registers the tools at import time.
from mcp_server import mcp

SEARCH_LAT, SEARCH_LNG = 40.0, -75.0


def call(coro_factory):
    """Run one client session and return its result.

    A fresh event loop per call, because Django's test runner is synchronous
    and there is no ambient loop to attach to.
    """

    async def run():
        async with Client(mcp) as client:
            return await coro_factory(client)

    return asyncio.run(run())


def payload_of(result):
    """The JSON body of a CallToolResult.

    Servers may return a parsed structured result, an unstructured text block,
    or both. Prefer the structured form and fall back to parsing the text, so
    the assertions don't depend on which one this server happens to send.
    """
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise AssertionError("tool returned no readable content")


class MCPDiscoveryTests(TransactionTestCase):
    """What a client learns before it calls anything."""

    def test_both_tools_and_the_resource_are_advertised(self):
        """The Phase 3 deliverable is 'two tools and a resource over MCP'. This
        is that sentence as an assertion — and it fails if a decorator is
        removed, which no test of the underlying services would notice."""
        tools = call(lambda client: client.list_tools())
        templates = call(lambda client: client.list_resource_templates())

        self.assertEqual(
            sorted(tool.name for tool in tools.tools), ["geo_search", "trust_check"]
        )
        self.assertIn(
            "listing://{listing_id}",
            [template.uri_template for template in templates.resource_templates],
        )

    def test_each_tool_publishes_a_usable_schema(self):
        """The schema is derived from the function signature, so a renamed
        parameter silently changes the contract every MCP client depends on."""
        tools = {tool.name: tool for tool in call(lambda c: c.list_tools()).tools}

        geo = tools["geo_search"].input_schema
        self.assertEqual(sorted(geo["required"]), ["lat", "lng"])
        for optional in ("radius_km", "category", "max_price", "limit"):
            self.assertIn(optional, geo["properties"])

        self.assertEqual(tools["trust_check"].input_schema["required"], ["listing_id"])

    def test_every_tool_carries_a_description(self):
        """An MCP tool with no description is one a model cannot choose
        correctly — the docstring is part of the interface, not commentary."""
        for tool in call(lambda client: client.list_tools()).tools:
            with self.subTest(tool=tool.name):
                self.assertTrue((tool.description or "").strip())


class MCPGeoSearchTests(TransactionTestCase):
    def setUp(self):
        self.lender = make_user("mcp-lender")
        self.near = make_listing(
            self.lender, "Nearby Drill", lat=40.01, lng=-75.01, price="20.00"
        )
        self.far = make_listing(
            self.lender, "Distant Drill", lat=41.5, lng=-75.0, price="20.00"
        )

    def test_returns_listings_near_a_point_nearest_first(self):
        result = call(
            lambda client: client.call_tool(
                "geo_search", {"lat": SEARCH_LAT, "lng": SEARCH_LNG, "radius_km": 5}
            )
        )
        body = payload_of(result)

        self.assertEqual([row["id"] for row in body["listings"]], [self.near.id])
        self.assertGreater(body["listings"][0]["distance_km"], 0)

    def test_the_response_carries_a_run_id_for_the_trace(self):
        """Every call mints a run_id and writes a TraceLog row with
        agent_name='mcp'. That is what makes a tool call arriving over the
        protocol auditable in the same way as an agent step."""
        from apps.core.models import TraceLog

        body = payload_of(
            call(
                lambda client: client.call_tool(
                    "geo_search", {"lat": SEARCH_LAT, "lng": SEARCH_LNG}
                )
            )
        )

        self.assertIn("run_id", body)
        row = TraceLog.objects.get(run_id=body["run_id"])
        self.assertEqual(row.agent_name, "mcp")
        self.assertEqual(row.tool_name, "geo_search")

    def test_a_category_filter_narrows_the_result(self):
        body = payload_of(
            call(
                lambda client: client.call_tool(
                    "geo_search",
                    {
                        "lat": SEARCH_LAT,
                        "lng": SEARCH_LNG,
                        "radius_km": 5,
                        "category": "electronics",
                    },
                )
            )
        )

        self.assertEqual(body["listings"], [])

    def test_impossible_geography_is_rejected_with_a_usable_message(self):
        """A tool that returns an empty list for lat=400 is unrecoverable by the
        caller; one that says what was wrong with which argument is not."""
        result = call(
            lambda client: client.call_tool("geo_search", {"lat": 400, "lng": 0})
        )

        self.assertTrue(result.is_error)
        self.assertIn("lat", str(result.content[0].text).lower())

    def test_an_unknown_category_is_rejected(self):
        result = call(
            lambda client: client.call_tool(
                "geo_search",
                {"lat": SEARCH_LAT, "lng": SEARCH_LNG, "category": "spaceships"},
            )
        )

        self.assertTrue(result.is_error)


class MCPTrustCheckTests(TransactionTestCase):
    def setUp(self):
        self.lender = make_user("mcp-lender")

    def test_a_clean_listing_reports_no_flags(self):
        listing = make_listing(self.lender, "Cordless Drill")

        body = payload_of(
            call(
                lambda client: client.call_tool(
                    "trust_check", {"listing_id": listing.id}
                )
            )
        )

        self.assertEqual(body["flags"], [])
        self.assertIsNone(body["highest_severity"])

    def test_a_flagged_listing_reports_the_rule_that_fired(self):
        """The structured shape is the point: a code a client can branch on, a
        severity, and the evidence that triggered it."""
        listing = make_listing(self.lender, "Basic Claw Hammer", price="1450.00")

        body = payload_of(
            call(
                lambda client: client.call_tool(
                    "trust_check", {"listing_id": listing.id}
                )
            )
        )

        self.assertEqual(
            [flag["code"] for flag in body["flags"]], ["price_out_of_range"]
        )
        self.assertEqual(body["highest_severity"], "high")
        self.assertEqual(body["flags"][0]["evidence"]["price"], 1450.0)

    def test_an_unknown_listing_returns_a_message_not_a_traceback(self):
        """check_listing_by_id raises TrustCheckError so the client gets
        'Listing 999999 not found.' rather than a DoesNotExist stack."""
        result = call(
            lambda client: client.call_tool("trust_check", {"listing_id": 999999})
        )

        self.assertTrue(result.is_error)
        self.assertIn("999999", str(result.content[0].text))


class MCPResourceTests(TransactionTestCase):
    def test_the_listing_resource_renders_one_listing(self):
        lender = make_user("mcp-lender")
        listing = make_listing(lender, "Cordless Drill")

        result = call(lambda client: client.read_resource(f"listing://{listing.id}"))
        text = result.contents[0].text

        self.assertIn("Cordless Drill", text)
        self.assertIn(f"Listing {listing.id}", text)

    def test_a_non_numeric_id_is_rejected(self):
        with self.assertRaises(Exception):
            call(lambda client: client.read_resource("listing://not-a-number"))
