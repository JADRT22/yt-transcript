"""Self-check: MCP tool surface stays coherent and unambiguous.

Run: python3 tests/test_tool_surface.py
"""

from __future__ import annotations

import asyncio

from yt_transcript.mcp_server import mcp

# The server is documented as a fixed 4-tool surface; changing the count is a
# deliberate API decision, so assert it rather than let it drift.
EXPECTED_TOOLS = {
    "get_transcript_tool",
    "list_transcripts_tool",
    "get_video_info_tool",
    "get_video_details_tool",
}

# get_video_info_tool returns a strict subset of get_video_details_tool's
# fields. When two tools overlap, each docstring has to route the agent to the
# other, or the agent has to guess — that guess is what cost this server its
# Glama disambiguation score.
ROUTING_PAIRS = [("get_video_info_tool", "get_video_details_tool")]


async def check() -> None:
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}

    missing = EXPECTED_TOOLS - by_name.keys()
    assert not missing, f"tools disappeared from MCP surface: {sorted(missing)}"

    for name in sorted(EXPECTED_TOOLS):
        tool = by_name[name]
        assert tool.description.strip(), f"{name} has an empty description"
        schema = tool.inputSchema
        assert schema.get("type") == "object", f"{name} schema is not an object"
        assert "properties" in schema, f"{name} schema has no properties"

    for caller, sibling in ROUTING_PAIRS:
        assert sibling in by_name[caller].description, (
            f"{caller} does not point the agent at {sibling}: with overlapping "
            f"return fields the agent would have to guess between them"
        )
        assert caller in by_name[sibling].description, (
            f"{sibling} does not point the agent back at {caller}"
        )


if __name__ == "__main__":
    asyncio.run(check())
    print(f"ok: {len(EXPECTED_TOOLS)} tools, descriptions and routing intact")
