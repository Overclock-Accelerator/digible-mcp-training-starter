"""Solo agent — one tool, and it does not know what a Spelling Bee is.

    python agent_solo.py
    python agent_solo.py --ask "what fits C_O__W_RD?"

Put this next to 02's agent_puzzlemaster.py and read the two system prompts.
That one is ~30 lines teaching the model to tell three games apart. This one
is four sentences, because there is nothing to tell apart: the server exposes
a single tool that takes English, so the only correct behaviour is to forward
the user's words verbatim and report what comes back.

Everything the other prompt taught — seven letters means Bee, underscores mean
crossword, "green, yellow, three blacks" means gybbb — still happens. It just
happens on the other side of the protocol now, where you cannot see it in the
trace and cannot fix it by editing this file.
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
MY_TOOL = "solve_puzzle"
DEFAULT_AGENT_NAME = "agent-solo"

# Four sentences. Compare with 02's agent_puzzlemaster.py.
SYSTEM_PROMPT = (
    "You are a word-puzzle assistant with exactly one tool, solve_puzzle. "
    "Pass the user's puzzle text to it VERBATIM — do not identify the game, do "
    "not extract letters or patterns or feedback strings, and do not reformat "
    "anything; the server does all of that. Always call the tool; never answer "
    'from your own knowledge. Pass agent_name="{agent_name}" on every call. '
    "The tool tells you which game it detected — report that alongside the "
    "answer so the user can see how their words were interpreted."
)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve any word puzzle — the SERVER works out which one.")
    parser.add_argument("--server", default="http://127.0.0.1:8020/mcp",
                        help="URL of the running MCP server")
    parser.add_argument("--ask", metavar="TEXT",
                        help="answer this one question and exit. Omit to open a chat.")
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME,
                        help="name this agent reports to the server's audit log")
    args = parser.parse_args()

    client = MultiServerMCPClient({
        "solo": {
            "transport": "streamable_http",
            "url": args.server,
        },
    })

    async with client.session("solo") as session:
        # No filtering to do — the server offers one solver, so this is the
        # whole surface. `routing_log` is dropped: it is for the operator
        # reading the audit trail, not for the agent answering a puzzle.
        tools = [t for t in await load_mcp_tools(session) if t.name == MY_TOOL]
        if not tools:
            print(f"error: server did not expose {MY_TOOL}", file=sys.stderr)
            return 1

        agent = create_agent(
            model="anthropic:claude-sonnet-5",
            tools=tools,
            system_prompt=SYSTEM_PROMPT.format(agent_name=args.agent_name),
        )

        # ainvoke, not invoke: MCP tools arrive as coroutine-only StructuredTools.
        if args.ask:
            print(f"\nyou › {args.ask}")
            print(await repl.once(agent, args.ask))
        else:
            await repl.chat(
                agent,
                title='Solo agent — the server picks the game',
                hints=[
                    "try:  today's bee is VALIDTY, V in the middle",
                    'then: what fits C_O__W_RD?',
                    'then: I played CRANE and got green, yellow, then three blacks',
                    'note: the tool call is solve_puzzle(...) every single time',
                ],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
