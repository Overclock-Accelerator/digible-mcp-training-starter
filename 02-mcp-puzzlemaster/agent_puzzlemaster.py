"""PuzzleMaster agent — one agent holding the WHOLE shared server.

    python agent_puzzlemaster.py
    python agent_puzzlemaster.py --ask "what fits C_O__W_RD?"

The other three agents in this folder each take one slice of the server:
agent_bee keeps `solve_spelling_bee` and throws the rest away, agent_crossword
keeps `solve_crossword_pattern`, agent_wordle keeps `solve_wordle`. Which game
you are playing is decided by which process you start.

This one keeps all three and lets the model decide. Say "I'm playing Wordle,
I opened with CRANE" and it routes on the descriptor; ask "what fits C_O__W_RD?"
with no descriptor at all and it routes on the shape of the question. Same
server, same dictionary, same audit table — the only thing that changed is that
tool *selection* is now the agent's job instead of the launcher's.

That is worth watching in the trace: with one tool the model cannot pick wrong,
so a correct call proves nothing. With three, the `show_tools` line is the first
place in this curriculum where the model's routing is actually on trial.
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

# Every solver the server exposes. The audit tools (usage_graph,
# export_results) are deliberately left out -- monitor.py owns those, and
# handing a puzzle agent a "chart my own usage" tool invites it to wander.
MY_TOOLS = ("solve_spelling_bee", "solve_crossword_pattern", "solve_wordle")
DEFAULT_AGENT_NAME = "agent-puzzlemaster"

# The routing prompt. Two jobs, in this order:
#
#   1. Honour a descriptor when one is given ("I'm playing the Bee...").
#   2. When none is given, route on the SHAPE of the input -- 7 letters plus a
#      center, an underscore pattern, or guesses paired with g/y/b feedback are
#      each unambiguous on their own.
#
# Asking a clarifying question is allowed but is the last resort, because the
# whole point of the folder is that the agent does the interpreting. It is
# spelled out rather than left implicit so the model does not open every turn
# with "which game are you playing?".
SYSTEM_PROMPT = f"""\
You are PuzzleMaster, a word-puzzle assistant with three tools:

- solve_spelling_bee(letters, center) — NYT Spelling Bee. Needs 7 distinct
  letters and which one is the mandatory center letter.
- solve_crossword_pattern(pattern) — a crossword slot written with letters and
  '_' for unknowns, e.g. C_O__W_RD. Length comes from the pattern.
- solve_wordle(guesses, feedback) — narrows 5-letter candidates. feedback is one
  string per guess using g (right letter, right spot), y (right letter, wrong
  spot), b (absent), e.g. "gybbb".

Choosing the tool is your job, not the user's.

If the user names the game, use that tool. If the user names no game, decide
from the shape of what they gave you:
  - seven letters and a "center"/"middle"/"must use" letter -> Spelling Bee
  - a pattern of letters and underscores, blanks, or dots -> crossword
  - one or more 5-letter guesses described with colours (green/yellow/
    grey/black/⬛🟨🟩) or a g/y/b string -> Wordle

Translate ordinary language into tool arguments yourself. "green, yellow, then
three blacks" is "gybbb". "V in the middle" means center="V". "C then O then two
blanks" is a pattern. Dots, dashes and question marks all mean '_'.

Ask a clarifying question only when the input genuinely fits no tool, and keep
it to one short sentence. Never guess or invent words yourself — the answer
always comes from a tool call.

Pass agent_name="{{agent_name}}" on every tool call.

Report the result plainly: for the Bee, the word count, total points and
pangrams; for a crossword, how many matched and the words; for Wordle, the
candidate count and a suggested next guess drawn from the candidates.
"""


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve any word puzzle via the shared PuzzleMaster MCP server.")
    parser.add_argument("--server", default="http://127.0.0.1:8002/mcp",
                        help="URL of the running MCP server")
    parser.add_argument("--ask", metavar="TEXT",
                        help="answer this one question and exit, e.g. "
                             '"I am playing Wordle, CRANE gave me gybbb". '
                             "Omit to open a chat.")
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
        # Unlike the three single-purpose agents, this one keeps every solver
        # the server offers. Same load_mcp_tools call, wider filter.
        tools = [t for t in await load_mcp_tools(session) if t.name in MY_TOOLS]
        missing = sorted(set(MY_TOOLS) - {t.name for t in tools})
        if missing:
            print(f"error: server did not expose {', '.join(missing)}", file=sys.stderr)
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
                title='PuzzleMaster — every tool on the shared server',
                hints=[
                    "try:  today's bee is VALIDTY, V in the middle",
                    'then: what fits C_O__W_RD?',
                    'then: I played CRANE and got green, yellow, then three blacks',
                ],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
