"""Regression tests for the canonical solvers. Run: python3 shared/test_solvers.py

Expected values below were derived by hand-tracing the Wordle rules and then
confirmed against the implementation. They exist because duplicate-letter
feedback is the single easiest thing to get subtly wrong.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import solvers_reference as s

FEEDBACK_CASES = [
    # (guess, answer, expected) -- greens claimed first, yellows from what's left
    ("ERASE", "SPEED", "ybbyy"),
    ("LEVEL", "LEDGE", "ggbyb"),
    ("SPEED", "ERASE", "ybyyb"),
    ("ALLOY", "LOYAL", "yyyyy"),
    ("CRANE", "CRANE", "ggggg"),
    ("FUZZY", "CRANE", "bbbbb"),
]

def main() -> int:
    words = s.load_words()
    failures = []

    for guess, answer, expected in FEEDBACK_CASES:
        got = s._score_guess(guess, answer)
        if got != expected:
            failures.append(f"_score_guess({guess},{answer}) = {got}, expected {expected}")

    # Spelling Bee, verified against the real 2026-08-28 NYT puzzle.
    # ENABLE1 over-generates vs NYT's curated list (21 words / 119 pts) --
    # that gap is a teaching point, not a bug.
    bee = s.solve_spelling_bee("VALIDTY", "V", words)
    if (bee["count"], bee["total_points"], bee["pangrams"]) != (34, 171, ["VALIDITY"]):
        failures.append(f"spelling bee VALIDTY/V drifted: {bee['count']}/{bee['total_points']}/{bee['pangrams']}")

    # 4-letter words score 1 point flat, not 4.
    if any(d["points"] != 1 for d in bee["words"] if len(d["word"]) == 4 and not d["pangram"]):
        failures.append("4-letter words must score 1 point flat")

    xw = s.solve_crossword_pattern("C_O__W_RD", words)
    if xw["matches"] != ["CROSSWORD"]:
        failures.append(f"crossword pattern drifted: {xw['matches']}")

    wd = s.solve_wordle(["CRANE"], ["gybbb"], words)
    if wd["count"] != 34 or "CHOIR" not in wd["candidates"]:
        failures.append(f"wordle CRANE/gybbb drifted: {wd['count']}")

    for line in failures:
        print("FAIL", line)
    print(f"{len(FEEDBACK_CASES) + 4 - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
