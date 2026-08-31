"""Agent plumbing — and *only* agent plumbing.

Note what this file does NOT hand out: a database connection, a month parser,
a property-name resolver. It carries argparse, key loading and the chat loop,
because none of that is what this exercise is about.

Everything to do with getting data out of `digible.db` is left to the six agent
files, and every one of them solves it differently. That is not a strawman: it
is what a codebase looks like when six people each shipped an agent in a
sprint, none of them wrong, none of them the same.

Run `python ../count_duplication.py` when you want the number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _shared_dir() -> Path:
    """Find the repo's shared/ directory by walking up, not by counting levels."""
    for d in Path(__file__).resolve().parents:
        if (d / "shared" / "envloader.py").is_file():
            return d / "shared"
    raise SystemExit(
        "could not find shared/envloader.py. Run this from inside the "
        "mcp-training repo."
    )


sys.path.insert(0, str(_shared_dir()))
import repl  # noqa: E402
from envloader import load_env, require  # noqa: E402

load_env()

run = repl.run  # re-exported so agents don't each import asyncio


def arg_parser(description: str) -> argparse.ArgumentParser:
    """Free-text question, optional.

    No arguments opens the conversation; a question answers once and exits.
    Quoting is optional — every remaining word is joined back together.

    Note what is NOT here: no `--property`, no `--month`, no defaults. Wiring an
    example value into argparse would mean the *caller* did the interpreting.
    """
    p = argparse.ArgumentParser(description=description)
    p.add_argument("question", nargs="*",
                   help="ask in plain English; omit entirely to open a chat")
    return p


def create_agent(**kwargs):
    """Thin passthrough so each agent can build its own agent visibly.

    The import guard lives here rather than in six files, but the
    create_agent() call itself stays in each agent -- because the folder is
    about seeing duplication, and hiding the agent construction would be the
    one piece of sprawl nobody could see.
    """
    try:
        from langchain.agents import create_agent as _ca
    except ModuleNotFoundError as exc:                 # wrong interpreter
        root = Path(__file__).resolve().parent.parent.parent
        raise SystemExit(
            f"error: {exc.name} is not installed in the Python you just used.\n"
            f"  This usually means a different virtualenv is active.\n"
            f"  Run it with the repo's own interpreter:\n"
            f"    {root}/.venv/bin/python {Path(sys.argv[0]).name}\n"
            f"  (or from the repo root: ./setup.sh && source .venv/bin/activate)"
        ) from None
    return _ca(**kwargs)


async def serve(system_prompt: str, tools: list, args, *,
                title: str, hints: list[str]) -> int:
    """Build the agent, then either answer once or open the conversation."""
    try:
        from langchain.agents import create_agent
    except ModuleNotFoundError as exc:                 # wrong interpreter
        root = Path(__file__).resolve().parent.parent.parent
        raise SystemExit(
            f"error: {exc.name} is not installed in the Python you just used.\n"
            f"  This usually means a different virtualenv is active.\n"
            f"  Run it with the repo's own interpreter:\n"
            f"    {root}/.venv/bin/python {Path(sys.argv[0]).name}\n"
            f"  (or from the repo root: ./setup.sh && source .venv/bin/activate)"
        ) from None

    require("ANTHROPIC_API_KEY")
    agent = create_agent(
        model="anthropic:claude-sonnet-5",
        tools=tools,
        system_prompt=system_prompt,
    )
    # ainvoke, not invoke — the whole repo is async so this stays true after the
    # tools move behind MCP and become coroutine-only StructuredTools.
    if repl.one_shot(args, "question"):
        print(await repl.once(agent, " ".join(args.question)))
        return 0
    return await repl.chat(agent, title=title, hints=hints)


COMMON_RULES = """
Always use your tools; never estimate a number yourself.
The data covers 14 properties, January through June 2026. If someone asks for a
month outside that, say so rather than guessing.
Be concise and lead with the number."""
