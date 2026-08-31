#!/usr/bin/env python3
"""`puzzle` — the same three solvers, behind a CLI instead of an MCP server.

This file is one half of the controlled experiment in 07. Every solver body
below is byte-identical to `shared/solvers_reference.py` (and therefore to the
bodies inside `02-mcp-puzzlemaster/mcp_server.py`). Nothing differs between the
two arms of the benchmark except the seam: argparse + stdout here, JSON-RPC
tool schemas over there.

    puzzle bee       --letters VALIDTY --center V [--json]
    puzzle crossword --pattern C_O__W_RD          [--json]
    puzzle wordle    --guess CRANE --feedback gybbb [--json]

`--json` emits exactly the dict the matching MCP tool returns, so the output
composes with jq. That composability is the whole argument this folder makes:

    puzzle bee --letters VALIDTY --center V --json \\
      | jq '[.words[] | select(.word | length >= 5)] | length'

Four bytes come back. With MCP, all 34 words land in the context window first.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WORDLIST = Path(__file__).resolve().parent.parent.parent / "shared" / "data" / "enable1.txt"


def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


# --------------------------------------------------------------------------
# Solver bodies — byte-identical to shared/solvers_reference.py.
# `verify_solvers.py` proves it programmatically; do not edit them here.
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
# The seam: argparse in, stdout out.
# --------------------------------------------------------------------------

def _emit(payload: dict, as_json: bool, render) -> None:
    if as_json:
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
    else:
        print(render(payload))


def _render_bee(r: dict) -> str:
    head = (f"{r['count']} words, {r['total_points']} points, "
            f"pangrams: {', '.join(r['pangrams']) or '(none)'}")
    body = "\n".join(f"  {d['word']:<12} {d['points']:>3}" for d in r["words"])
    return f"{head}\n{body}" if body else head


def _render_crossword(r: dict) -> str:
    head = f"{r['pattern']} (length {r['length']}) -> {r['count']} match(es)"
    return head + ("\n  " + "\n  ".join(r["matches"]) if r["matches"] else "")


def _render_wordle(r: dict) -> str:
    head = f"{r['count']} candidate(s)"
    return head + ("\n  " + "\n  ".join(r["candidates"]) if r["candidates"] else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="puzzle",
        description="Word-puzzle solvers over the ENABLE1 dictionary (172,823 words).",
    )
    # --json is declared per-subcommand, not here: a subparser would otherwise
    # overwrite the top-level value with its own default and silently ignore it.
    sub = parser.add_subparsers(dest="command", required=True)

    bee = sub.add_parser("bee", help="solve a NYT Spelling Bee puzzle and score it")
    bee.add_argument("--letters", required=True, help="the 7 puzzle letters, e.g. VALIDTY")
    bee.add_argument("--center", required=True, help="the mandatory center letter, e.g. V")
    bee.add_argument("--json", action="store_true", help="emit JSON")

    cw = sub.add_parser("crossword", help="find words matching a crossword pattern")
    cw.add_argument("--pattern", required=True,
                    help="letters with '_' for unknowns, e.g. C_O__W_RD; length comes from the pattern")
    cw.add_argument("--json", action="store_true", help="emit JSON")

    wd = sub.add_parser("wordle", help="narrow Wordle candidates from guesses and feedback")
    wd.add_argument("--guess", action="append", required=True, metavar="WORD",
                    help="a word already guessed; repeat once per guess")
    wd.add_argument("--feedback", action="append", required=True, metavar="GYB",
                    help="feedback for the matching --guess: g=right spot, y=wrong spot, b=absent")
    wd.add_argument("--length", type=int, default=5, help="word length (default 5)")
    wd.add_argument("--json", action="store_true", help="emit JSON")

    args = parser.parse_args(argv)
    as_json = args.json

    words = load_words()
    try:
        if args.command == "bee":
            _emit(solve_spelling_bee(args.letters, args.center, words), as_json, _render_bee)
        elif args.command == "crossword":
            _emit(solve_crossword_pattern(args.pattern, words), as_json, _render_crossword)
        else:
            _emit(solve_wordle(args.guess, args.feedback, words, args.length),
                  as_json, _render_wordle)
    except ValueError as exc:
        print(f"puzzle: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
