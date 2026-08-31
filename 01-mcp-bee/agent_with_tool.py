#!/usr/bin/env python3
"""BEFORE: a LangChain agent with the Spelling Bee solver as a LOCAL tool.

The solver lives in this file. It works. Nothing is wrong with it -- until a
second consumer wants the same capability. Compare with agent_with_mcp.py:

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
from langchain.tools import tool

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

# ==========================================================================
# The solver. This block is copied VERBATIM into mcp_server.py.
# Nothing below this line changes when the tool moves behind MCP.
# ==========================================================================

WORDLIST = Path(__file__).parent.parent / "shared" / "data" / "enable1.txt"


def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


def solve_spelling_bee(letters: str, center: str, words: list[str]) -> dict:
    """Find every valid NYT Spelling Bee word and score it.

    Rules: words are >= 4 letters, must contain the center letter, and may use
    ONLY the 7 allowed letters -- but may reuse them freely. Hence a set
    subset test, not a multiset one.

    Scoring: a 4-letter word is worth 1 point flat. A 5+ letter word is worth
    1 point per letter. A pangram (uses all 7 letters) earns +7 on top.
    """
    allowed = set(letters.upper())
    center = center.upper()
    if len(allowed) != 7:
        raise ValueError(f"need exactly 7 distinct letters, got {len(allowed)}")
    if center not in allowed:
        raise ValueError(f"center letter {center!r} must be one of {letters!r}")

    found = []
    for w in words:
        if len(w) >= 4 and center in w and set(w) <= allowed:
            pangram = set(w) == allowed
            points = (1 if len(w) == 4 else len(w)) + (7 if pangram else 0)
            found.append({"word": w, "points": points, "pangram": pangram})

    found.sort(key=lambda d: (-d["points"], d["word"]))
    return {
        "words": found,
        "count": len(found),
        "total_points": sum(d["points"] for d in found),
        "pangrams": [d["word"] for d in found if d["pangram"]],
    }


# ==========================================================================
# The seam. THIS is the only part that moves in agent_with_mcp.py.
# ==========================================================================

@tool
def spelling_bee(letters: str, center: str, agent_name: str) -> dict:
    """Solve a NYT Spelling Bee puzzle and score every answer.

    Use this whenever asked to find the words in a Spelling Bee puzzle. Do not
    try to work the puzzle out yourself -- the word list is authoritative.

    Args:
        letters: The 7 puzzle letters, e.g. "VALIDTY". Order does not matter.
        center: The single mandatory center letter, e.g. "V".
        agent_name: Your own name, for attribution in the server's logs.

    Returns a dict with "words" (each {word, points, pangram}), "count",
    "total_points", and "pangrams".
    """
    log.info("spelling_bee letters=%s center=%s agent_name=%s", letters, center, agent_name)
    return solve_spelling_bee(letters, center, load_words())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Solve a Spelling Bee puzzle with an agent.")
    p.add_argument("--letters", help="the 7 puzzle letters (omit to open a conversation)")
    p.add_argument("--center", help="the mandatory center letter")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    question = f"Solve the Spelling Bee with letters {args.letters} and center letter {args.center}."

    tools = [spelling_bee]

    agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)
    if getattr(args, "question", None) or repl.one_shot(args, 'letters', 'center'):
        question = getattr(args, "question", None) or question
        print(f"\nyou › {question}")
        print(await repl.once(agent, question))
    else:
        await repl.chat(
                agent,
                title='Spelling Bee agent — LOCAL tool',
                hints=[
                "try:  today's bee is VALIDTY, V in the middle",
                'then: now LAMPYRD with Y in the centre',
                'then: which had more words?',
                ],
            )


if __name__ == "__main__":
    asyncio.run(main())
