"""Read the routing audit trail — no agent, no network, no API key needed.

    python monitor.py --log
    python monitor.py --log --limit 50
    python monitor.py --cost

This is where a server-side misroute becomes visible. In 02 the agent's own
trace showed which tool was chosen, so `monitor.py` there only had to count
calls. Here the choice happened inside the server and the client was never
told, so reading this table is the ONLY way to audit it.

Like 02's monitor, it drives the same MCP tool an agent could call, through
FastMCP's in-memory Client — so it needs no running server.
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3

from fastmcp import Client

import mcp_server


def cost_report() -> str:
    """Contrast time spent routing against time spent solving.

    The single most useful number in this folder. Routing is a round trip to a
    language model; solving is a list comprehension. Print both.
    """
    with mcp_server._db_lock, mcp_server._connect() as conn:
        rows = conn.execute(
            "SELECT game, COUNT(*), SUM(route_ms), SUM(solve_ms), SUM(ok)"
            " FROM invocations GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()

    if not rows:
        return "No invocations logged yet. Run agent_solo.py, then ask again."

    lines = [
        f"{'game':<14} {'calls':>5} {'route':>9} {'solve':>8} {'ratio':>8}",
        "-" * 48,
    ]
    t_route = t_solve = t_calls = 0
    for game, count, route, solve, oks in rows:
        route, solve = route or 0, solve or 0
        t_route, t_solve, t_calls = t_route + route, t_solve + solve, t_calls + count
        ratio = f"{route / solve:.0f}x" if solve else "--"
        lines.append(f"{game:<14} {count:>5} {route / count:>7.0f}ms "
                     f"{solve / count:>6.0f}ms {ratio:>8}")
    lines += [
        "-" * 48,
        f"{'all':<14} {t_calls:>5} {t_route / t_calls:>7.0f}ms "
        f"{t_solve / t_calls:>6.0f}ms "
        f"{(f'{t_route / t_solve:.0f}x' if t_solve else '--'):>8}",
        "",
        "route = deciding which game it was (a Claude call, in the server).",
        "solve = actually answering it (a list comprehension over 172k words).",
    ]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the routing audit trail.")
    parser.add_argument("--log", action="store_true",
                        help="show recent routing decisions and the stated reason")
    parser.add_argument("--cost", action="store_true",
                        help="compare time spent routing vs time spent solving")
    parser.add_argument("--limit", type=int, default=20,
                        help="how many rows for --log. Defaults to 20.")
    parser.add_argument("--agent-name", default="monitor",
                        help="name to record for this monitoring call")
    args = parser.parse_args()

    if not args.log and not args.cost:
        parser.error("give --log and/or --cost")

    if args.log:
        # Through the MCP tool, exactly as an agent would reach it.
        async with Client(mcp_server.mcp) as client:
            result = await client.call_tool(
                "routing_log", {"agent_name": args.agent_name, "limit": args.limit})
            print(result.content[0].text)
    if args.cost:
        if args.log:
            print()
        # Straight SQL: this one is an operator's view, not a tool an agent
        # should be able to call.
        print(cost_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
