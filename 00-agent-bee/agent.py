"""A LangChain agent with one local tool: a Spelling Bee solver.

This is the ordinary way to give a model a capability -- a Python function in
the same file as the agent, wrapped in @tool. It works, it is deterministic,
and it is the shape most agents in the wild have.

Run:
    python agent.py --letters VALIDTY --center V
    python agent.py --question "Which VALIDTY/center-V words are worth 10+?"
"""

import argparse
import asyncio
import json
import os
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
import repl  # noqa: E402

load_env()

# The word list is resolved relative to THIS file, so the agent runs correctly
# from any working directory.
WORDLIST = Path(__file__).resolve().parent.parent / "shared" / "data" / "enable1.txt"


def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


# ==========================================================================
# THE SOLVER -- copied verbatim from shared/solvers_reference.py.
# Not one character of this function changes anywhere in this curriculum.
# ==========================================================================

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
# THE SEAM -- what turns that function into something the model can call.
# The docstring and the type hints below ARE the schema the model sees.
# ==========================================================================

@tool
def spelling_bee(letters: str, center: str) -> dict:
    """Solve a NYT Spelling Bee puzzle exhaustively and score every answer.

    Args:
        letters: The 7 puzzle letters as one string, e.g. "VALIDTY".
        center: The mandatory center letter, e.g. "V". Must be one of `letters`.

    Returns:
        A dict with `words` (each with its `points` and whether it is a
        `pangram`), `count`, `total_points`, and the list of `pangrams`.
    """
    result = solve_spelling_bee(letters, center, load_words())
    return result


SYSTEM_PROMPT = (
    "You are a puzzle assistant. You have a spelling_bee tool that solves NYT "
    "Spelling Bee puzzles exhaustively. Always use the tool rather than guessing "
    "words yourself -- the tool is the source of truth. Report the counts and "
    "pangrams it returns exactly as given."
)


def check_puzzle(letters: str, center: str) -> None:
    """Pre-flight the puzzle so a typo fails fast instead of costing an API call."""
    allowed = set(letters.upper())
    if len(allowed) != 7:
        sys.exit(f"error: --letters needs exactly 7 distinct letters, "
                 f"got {len(allowed)} in {letters!r}")
    if center.upper() not in allowed:
        sys.exit(f"error: --center {center!r} must be one of the letters {letters!r}")


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="A LangChain agent with a local Spelling Bee tool. "
                    "Run with no arguments to open a conversation.")
    parser.add_argument("--letters", help="the 7 puzzle letters, e.g. VALIDTY")
    parser.add_argument("--center", help="the mandatory center letter, e.g. V")
    parser.add_argument("--question", help="ask one question and exit")
    args = parser.parse_args()

    require("ANTHROPIC_API_KEY")

    agent = create_agent("anthropic:claude-sonnet-5", [spelling_bee],
                         system_prompt=SYSTEM_PROMPT)

    # One-shot mode: arguments given, answer and exit. Used by samples and tests.
    if args.question or (args.letters and args.center):
        if args.letters and args.center:
            check_puzzle(args.letters, args.center)
        question = args.question or (
            f"Solve the Spelling Bee for letters {args.letters} with center "
            f"letter {args.center}. How many words, how many points, "
            f"and what are the pangrams?")
        print(f"\nyou › {question}")
        print(await repl.once(agent, question))
        return 0

    # No arguments: open a conversation. The agent has to work out which
    # puzzle you mean and pull the letters out of what you typed -- that
    # interpretation is the part a --letters flag hides.
    return await repl.chat(
        agent,
        title="Spelling Bee agent — one local tool",
        hints=[
            'try:  today\'s bee is VALIDTY, V in the middle',
            'then: how about LAMPYRD with the Y in the centre?',
            'then: which of those had more pangrams?',
        ],
    )


if __name__ == "__main__":
    raise SystemExit(repl.run(main()))
