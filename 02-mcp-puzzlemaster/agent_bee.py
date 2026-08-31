"""Spelling Bee agent — one of three consumers of the shared PuzzleMaster server.

    python agent_bee.py --letters VALIDTY --center V

Structurally identical to agent_crossword.py and agent_wordle.py. The only
differences are which tool it asks for and what it puts in the prompt. That is
the point: three agents, one server, one dictionary.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

try:
    from langchain.agents import create_agent
except ModuleNotFoundError as exc:  # wrong interpreter, or setup not run
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    raise SystemExit(
        f"error: {exc.name} is not installed in the Python you just used.\n"
        f"  This usually means a different virtualenv is active.\n"
        f"  Run it with the repo's own interpreter, which always works:\n"
        f"    {root}/.venv/bin/python {pathlib.Path(__file__).name}\n"
        f"  (or from the repo root: ./setup.sh && source .venv/bin/activate)"
    ) from None
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

# Load ANTHROPIC_API_KEY from .env.local at the repo root (see shared/envloader.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from envloader import load_env, require  # noqa: E402
from toolvis import show_tools  # noqa: E402
import repl  # noqa: E402

load_env()

SERVER = Path(__file__).parent / "mcp_server.py"
MY_TOOL = "solve_spelling_bee"
DEFAULT_AGENT_NAME = "agent-bee"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Solve a NYT Spelling Bee via MCP.")
    parser.add_argument("--server", default="http://127.0.0.1:8002/mcp",
                        help="URL of the running MCP server")
    parser.add_argument("--letters", help="the 7 puzzle letters, e.g. VALIDTY")
    parser.add_argument("--center", help="the mandatory center letter, e.g. V")
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME,
                        help="name this agent reports to the server's audit log")
    args = parser.parse_args()

    client = MultiServerMCPClient({
        "puzzlemaster": {
            "transport": "streamable_http",
            "url": args.server,
        },
    })

    # One session for the whole run: the server subprocess starts once, so the
    # 172k-word dictionary is loaded once no matter how many tool calls the
    # model makes. Reconnecting per call would reload it every time.
    async with client.session("puzzlemaster") as session:
        # Ask the shared server for every tool, then keep only this agent's own.
        # Same server, different slice of it per agent.
        tools = [t for t in await load_mcp_tools(session) if t.name == MY_TOOL]
        if not tools:
            print(f"error: server did not expose {MY_TOOL}", file=sys.stderr)
            return 1

        agent = create_agent(
            model="anthropic:claude-sonnet-5",
            tools=tools,
            system_prompt=(
                "You are a Spelling Bee assistant. Always use the tool to solve; never "
                f"guess words yourself. Pass agent_name=\"{args.agent_name}\" on every "
                "tool call. Report the word count, the total points, and the pangrams."
            ),
        )

        # ainvoke, not invoke: MCP tools arrive as coroutine-only StructuredTools.
        if getattr(args, "question", None) or repl.one_shot(args, 'letters', 'center'):
            question = getattr(args, "question", None) or f"Solve the Spelling Bee with letters {args.letters} and center letter {args.center}."
            print(f"\nyou › {question}")
            print(await repl.once(agent, question))
        else:
            await repl.chat(
                    agent,
                    title='Bee agent — shared PuzzleMaster server',
                    hints=[
                    "try:  today's bee is VALIDTY, V in the middle",
                    'then: and LAMPYRD, Y in the centre',
                    ],
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
