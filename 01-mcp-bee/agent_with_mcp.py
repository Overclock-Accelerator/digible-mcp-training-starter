#!/usr/bin/env python3
"""AFTER: the same LangChain agent, with the solver behind an MCP server.

The solver is gone from this file. It lives in mcp_server.py, which this script
launches over stdio. Compare with agent_with_tool.py:

    diff agent_with_tool.py agent_with_mcp.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
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

# Load ANTHROPIC_API_KEY from .env.local at the repo root (see shared/envloader.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from envloader import load_env, require  # noqa: E402
from toolvis import show_tools  # noqa: E402
import repl  # noqa: E402

load_env()

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bee")

MODEL = "anthropic:claude-sonnet-5"
AGENT_NAME = "bee-agent"
SYSTEM_PROMPT = (
    "You are a Spelling Bee assistant. Always use the spelling_bee tool -- never "
    f"work the puzzle out yourself. Pass agent_name={AGENT_NAME!r} on every call. "
    "Report the word count, the total points, and the pangram(s)."
)

SERVER = Path(__file__).parent / "mcp_server.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Solve a Spelling Bee puzzle with an agent.")
    p.add_argument("--letters", help="the 7 puzzle letters (omit to open a conversation)")
    p.add_argument("--center", help="the mandatory center letter")
    p.add_argument("--server", default="http://127.0.0.1:8001/mcp",
                   help="URL of the MCP server you started in the other terminal")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    question = f"Solve the Spelling Bee with letters {args.letters} and center letter {args.center}."

    client = MultiServerMCPClient({
        "bee": {
            "transport": "streamable_http",
            "url": args.server,
        },
    })
    try:
        tools = await client.get_tools()
    except Exception as exc:
        raise SystemExit(
            f"error: could not reach the MCP server at {args.server}\n"
            f"  ({type(exc).__name__}: {exc})\n\n"
            f"  Start it in another terminal first — it is a separate process:\n"
            f"    ./.venv/bin/python {'01-mcp-bee/mcp_server.py'}\n"
        ) from None

    agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)
    if getattr(args, "question", None) or repl.one_shot(args, 'letters', 'center'):
        question = getattr(args, "question", None) or question
        print(f"\nyou › {question}")
        print(await repl.once(agent, question))
    else:
        await repl.chat(
                agent,
                title='Spelling Bee agent — tool from an MCP SERVER',
                hints=[
                "try:  today's bee is VALIDTY, V in the middle",
                'then: now LAMPYRD with Y in the centre',
                'same conversation, same answers — only the seam moved',
                ],
            )


if __name__ == "__main__":
    asyncio.run(main())
