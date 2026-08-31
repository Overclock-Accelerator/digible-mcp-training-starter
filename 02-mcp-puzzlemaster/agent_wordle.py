"""Wordle agent — one of three consumers of the shared PuzzleMaster server.

    python agent_wordle.py --guess CRANE --feedback gybbb

Repeat --guess/--feedback in matching order for multiple turns. Structurally
identical to agent_bee.py and agent_crossword.py. The only differences are
which tool it asks for and what it puts in the prompt. That is the point:
three agents, one server, one dictionary.
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
MY_TOOL = "solve_wordle"
DEFAULT_AGENT_NAME = "agent-wordle"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Narrow Wordle candidates via MCP.")
    parser.add_argument("--server", default="http://127.0.0.1:8002/mcp",
                        help="URL of the running MCP server")
    parser.add_argument("--guess", action="append", metavar="WORD",
                        help="a word already guessed; repeatable")
    parser.add_argument("--feedback", action="append", metavar="GYB",
                        help="feedback for the matching guess, e.g. gybbb; repeatable")
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME,
                        help="name this agent reports to the server's audit log")
    args = parser.parse_args()

    if len(args.guess or []) != len(args.feedback or []):
        parser.error("--guess and --feedback must be given the same number of times")

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
                "You are a Wordle assistant. Always use the tool to narrow candidates; "
                f"never reason about letters yourself. Pass agent_name=\"{args.agent_name}\" "
                "on every tool call. Report the candidate count and suggest a next guess "
                "from the candidates."
            ),
        )

        turns = ", ".join(f"{g} -> {f}" for g, f in zip(args.guess or [], args.feedback or []))
        # ainvoke, not invoke: MCP tools arrive as coroutine-only StructuredTools.
        if getattr(args, "question", None) or repl.one_shot(args, 'guess', 'feedback'):
            question = getattr(args, "question", None) or f"My Wordle guesses so far: {turns}. What words are still possible?"
            print(f"\nyou › {question}")
            print(await repl.once(agent, question))
        else:
            await repl.chat(
                    agent,
                    title='Wordle agent — shared PuzzleMaster server',
                    hints=[
                    'try:  I played CRANE and got green-yellow-black-black-black',
                    'then: then I tried CHOIR, all black except the C',
                    ],
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
