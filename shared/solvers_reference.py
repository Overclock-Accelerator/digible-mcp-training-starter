"""Canonical solver implementations for mcp-training.

These three function bodies are the SPINE of the whole curriculum. They are
copied VERBATIM into every folder — as local agent tools in 00, and as
@mcp.tool bodies in 01 and 02. The lesson only lands if the code is provably
identical on both sides of the refactor, so do not "improve" them per-folder.

All three read one word list: shared/data/enable1.txt (ENABLE1, public domain).
"""

from collections import Counter
from pathlib import Path

WORDLIST = Path(__file__).parent / "data" / "enable1.txt"


def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


# --------------------------------------------------------------------------
# Spelling Bee
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
