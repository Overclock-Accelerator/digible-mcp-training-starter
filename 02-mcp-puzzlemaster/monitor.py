"""Read the shared server's audit trail — no API key, no model, no network.

    python monitor.py --graph agent
    python monitor.py --graph tool
    python monitor.py --export results.csv

The three agents are the *writers* of the audit trail; this is the reader. It
calls the very same `usage_graph` and `export_results` MCP tools the agents
could call, through FastMCP's in-memory Client, which is why running it also
adds a row of its own under the agent name you pass (default "monitor"). The
audit trail audits the audit tools too — that is the honest behaviour, not a
bug.
"""

from __future__ import annotations

import argparse
import asyncio

from fastmcp import Client

import mcp_server


async def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect usage.db via the MCP tools.")
    parser.add_argument("--graph", choices=("agent", "tool"),
                        help="render the ASCII usage chart grouped by agent or tool")
    parser.add_argument("--export", metavar="PATH",
                        help="write every logged invocation to this CSV")
    parser.add_argument("--agent-name", default="monitor",
                        help="name to record for this monitoring call")
    args = parser.parse_args()

    if not args.graph and not args.export:
        parser.error("give --graph and/or --export")

    async with Client(mcp_server.mcp) as client:
        if args.graph:
            result = await client.call_tool(
                "usage_graph", {"agent_name": args.agent_name, "group_by": args.graph})
            print(result.content[0].text)
        if args.export:
            result = await client.call_tool(
                "export_results", {"agent_name": args.agent_name, "path": args.export})
            print(f"wrote {result.data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
