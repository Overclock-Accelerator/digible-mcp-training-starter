"""Generate a realistic multi-agent usage history WITHOUT an API key.

    python seed_usage.py            # add ~25 invocations to usage.db
    python seed_usage.py --reset    # wipe usage.db first

Why this exists: the monitoring demo is the part of a live session most likely
to break, because it is the part that needs three agents, a network, and a
working ANTHROPIC_API_KEY. This script drives the same server through FastMCP's
in-memory Client — same tools, same middleware, same SQLite rows — so
`usage_graph` and `export_results` always have something to show.

It calls the tools directly rather than through a model, so the counts are
deliberately lopsided (a bar chart of three equal bars teaches nothing) and a
couple of calls fail on purpose to prove failures are logged with ok=0.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from fastmcp import Client

import mcp_server

# (agent_name, tool, arguments) — repetition is intentional; real usage is spiky.
CALLS: list[tuple[str, str, dict]] = (
    [("agent-wordle", "solve_wordle",
      {"guesses": ["CRANE"], "feedback": [fb]})
     for fb in ("gybbb", "bbbbb", "ybbbb", "bybbb", "bbybb", "ggbbb", "bbbgg")]
    + [("agent-wordle", "solve_wordle",
        {"guesses": ["CRANE", "SLOTH"], "feedback": ["bbbbb", fb]})
       for fb in ("bgbbb", "gbbbb", "bbgbb", "ybbby")]
    + [("agent-bee", "solve_spelling_bee", {"letters": letters, "center": center})
       for letters, center in (("VALIDTY", "V"), ("VALIDTY", "A"), ("CROSWDE", "C"),
                               ("PLANTER", "P"), ("MONSTER", "M"), ("BUCKLED", "K"))]
    + [("agent-crossword", "solve_crossword_pattern", {"pattern": pattern})
       for pattern in ("C_O__W_RD", "P_ZZL_", "_ORDL_", "M_STER")]
    # Failures — an audit trail that only records successes is not an audit trail.
    + [("agent-bee", "solve_spelling_bee", {"letters": "ABC", "center": "A"}),
       ("agent-crossword", "solve_crossword_pattern", {"pattern": "C_O!!W_RD"}),
       ("agent-wordle", "solve_wordle",
        {"guesses": ["CRANE"], "feedback": ["gybbb", "bbbbb"]})]
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true",
                        help="delete existing rows before seeding")
    args = parser.parse_args()

    if args.reset:
        with mcp_server._db_lock, mcp_server._connect() as conn:
            conn.execute("DELETE FROM invocations")
        print("cleared usage.db")

    ok = failed = 0
    # Client(server) talks to the server object in-process: no subprocess, no
    # network, no API key -- but every call still crosses the same middleware.
    async with Client(mcp_server.mcp) as client:
        for agent_name, tool, arguments in CALLS:
            try:
                await client.call_tool(tool, {"agent_name": agent_name, **arguments})
                ok += 1
            except Exception as exc:                  # noqa: BLE001 - expected here
                failed += 1
                print(f"  expected failure: {tool} -> {exc}", file=sys.stderr)

        print(f"seeded {ok + failed} invocations ({ok} ok, {failed} failed)\n")
        graph = await client.call_tool(
            "usage_graph", {"agent_name": "seed", "group_by": "agent"})
        print(graph.content[0].text)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
