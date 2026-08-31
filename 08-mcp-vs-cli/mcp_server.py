"""The MCP arm of the benchmark — the same three solvers, plus a tool-count knob.

    python mcp_server.py --tools 3     # just the three real solvers
    python mcp_server.py --tools 40    # the three, plus 37 plausible dummies

The knob exists to measure one thing: **tool definitions are a per-request tax.**
Every tool's name, description and full JSON schema is serialized into the
system portion of *every* request, whether or not the model calls it. Padding
the server with realistic-looking extra tools and re-running an identical task
turns "don't over-wrap things in MCP" from advice into arithmetic.

The pad tools are deliberately plausible — the kind of thing a team actually
ships on a word-utilities server — with real parameters and real docstrings, so
their schema cost is representative rather than a strawman of one-line stubs.

Solver bodies are byte-identical to `shared/solvers_reference.py`; see
`verify_solvers.py`. Never print to stdout here — stdout IS the stdio protocol
channel.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

HERE = Path(__file__).resolve().parent
WORDLIST = HERE.parent / "shared" / "data" / "enable1.txt"


def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


WORDS = load_words()


# --------------------------------------------------------------------------
# Solver bodies — byte-identical to shared/solvers_reference.py.
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Crossword
# --------------------------------------------------------------------------

def solve_crossword_pattern(pattern: str, words: list[str]) -> dict:
    """Find words matching a crossword pattern like 'C_O__W_RD'.

    Underscore means unknown. Word length is derived from the pattern, so the
    caller never passes a separate length argument.
    """
    pat = pattern.strip().upper()
    if not pat:
        raise ValueError("pattern must not be empty")
    if not all(c.isalpha() or c == "_" for c in pat):
        raise ValueError("pattern may contain only letters and underscores")

    matches = [
        w for w in words
        if len(w) == len(pat)
        and all(p == "_" or p == c for p, c in zip(pat, w))
    ]
    return {"pattern": pat, "length": len(pat), "matches": matches, "count": len(matches)}


# --------------------------------------------------------------------------
# Wordle
# --------------------------------------------------------------------------

def _score_guess(guess: str, answer: str) -> str:
    """Return Wordle feedback for a guess against a known answer.

    Greens are assigned first, then yellows are drawn from the REMAINING
    letters of the answer. That two-pass order is what makes duplicate
    letters behave correctly -- the classic Wordle solver bug is doing it
    in one pass.
    """
    result = ["b"] * len(guess)
    pool = Counter()
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            result[i] = "g"
        else:
            pool[a] += 1
    for i, g in enumerate(guess):
        if result[i] == "b" and pool[g] > 0:
            result[i] = "y"
            pool[g] -= 1
    return "".join(result)


def solve_wordle(guesses: list[str], feedback: list[str], words: list[str],
                 length: int = 5) -> dict:
    """Narrow the candidate list from past Wordle guesses and their feedback.

    Feedback uses 'g' (right letter, right spot), 'y' (right letter, wrong
    spot), 'b' (letter absent).

    Rather than hand-coding constraint rules -- which is where duplicate
    letters go wrong -- a candidate survives only if replaying each guess
    against it reproduces exactly the feedback that was actually seen.
    """
    if len(guesses) != len(feedback):
        raise ValueError("guesses and feedback must be the same length")

    guesses = [g.strip().upper() for g in guesses]
    feedback = [f.strip().lower() for f in feedback]
    for g, f in zip(guesses, feedback):
        if len(g) != length or len(f) != length:
            raise ValueError(f"{g!r}/{f!r} must both be {length} characters")
        if not set(f) <= {"g", "y", "b"}:
            raise ValueError(f"feedback {f!r} may only contain g, y, b")

    candidates = [w for w in words if len(w) == length]
    for g, f in zip(guesses, feedback):
        candidates = [c for c in candidates if _score_guess(g, c) == f]

    return {"candidates": candidates, "count": len(candidates)}


# --------------------------------------------------------------------------
# The seam: @mcp.tool wrappers. Same three functions, now with schemas.
# --------------------------------------------------------------------------

mcp = FastMCP("puzzlebench")


@mcp.tool(name="solve_spelling_bee")
def solve_spelling_bee_tool(agent_name: str, letters: str, center: str) -> dict:
    """Solve a NYT Spelling Bee puzzle against the full ENABLE1 dictionary.

    Args:
        agent_name: The name of the calling agent, e.g. "agent-bee".
        letters: The 7 puzzle letters, e.g. "VALIDTY".
        center: The mandatory center letter, e.g. "V".

    Returns every valid word with its score, the total, and any pangrams.
    """
    try:
        return solve_spelling_bee(letters, center, WORDS)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(name="solve_crossword_pattern")
def solve_crossword_pattern_tool(agent_name: str, pattern: str) -> dict:
    """Find dictionary words matching a crossword pattern.

    Args:
        agent_name: The name of the calling agent, e.g. "agent-crossword".
        pattern: Letters with '_' for unknowns, e.g. "C_O__W_RD". The word
            length comes from the pattern, so do not pass a length.
    """
    try:
        return solve_crossword_pattern(pattern, WORDS)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(name="solve_wordle")
def solve_wordle_tool(agent_name: str, guesses: list[str], feedback: list[str],
                      length: int = 5) -> dict:
    """Narrow the Wordle candidate list from past guesses and their feedback.

    Args:
        agent_name: The name of the calling agent, e.g. "agent-wordle".
        guesses: The words already guessed, e.g. ["CRANE"].
        feedback: One string per guess, same length as the word, using
            'g' (right letter, right spot), 'y' (right letter, wrong spot),
            'b' (letter absent) — e.g. ["gybbb"].
        length: Word length. Defaults to 5.
    """
    try:
        return solve_wordle(guesses, feedback, WORDS, length)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


REAL_TOOLS = ["solve_spelling_bee", "solve_crossword_pattern", "solve_wordle"]


# --------------------------------------------------------------------------
# The pad. 37 plausible word-utility capabilities, shared with the CLI arm via
# pad_catalog so both sides pad with the same 37 things — otherwise the two
# lines on the chart are not measuring the same axis.
# --------------------------------------------------------------------------

from pad_catalog import PAD_TOOLS  # noqa: E402




def _register_pad(count: int) -> None:
    """Register `count` pad tools. They raise if called — the benchmark tasks
    never need them, and a tool that silently returns junk would be worse than
    one that says plainly that it is scenery."""
    if count > len(PAD_TOOLS):
        raise SystemExit(f"only {len(PAD_TOOLS)} pad tools available, asked for {count}")
    for name, params, doc in PAD_TOOLS[:count]:
        src = (
            f"def {name}(agent_name: str, {params}) -> dict:\n"
            f'    """{doc}\n    """\n'
            f'    raise ToolError("{name} is a benchmark pad tool and has no implementation")\n'
        )
        ns: dict = {"ToolError": ToolError}
        exec(compile(src, f"<pad:{name}>", "exec"), ns)
        mcp.tool(name=name)(ns[name])


def main() -> None:
    parser = argparse.ArgumentParser(description="PuzzleBench MCP server with a tool-count knob.")
    parser.add_argument("--tools", type=int, default=3,
                        help="total tools to expose: the 3 real solvers plus pad (default 3)")
    args = parser.parse_args()

    pad = args.tools - len(REAL_TOOLS)
    if pad < 0:
        raise SystemExit(f"--tools must be at least {len(REAL_TOOLS)} (the real solvers)")
    _register_pad(pad)
    print(f"[puzzlebench] serving {args.tools} tools ({pad} pad)", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
