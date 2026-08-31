"""PuzzleMaster Solo — the server works out which game you are playing.

The ONE idea: routing is a design decision, not a fact of nature. In 02 the
server exposes three solvers and the *agent's* model picks between them. Here
the server exposes exactly ONE tool, `solve_puzzle(puzzle)`, takes raw English,
and does the classifying itself — with its own Claude call, behind the
protocol, where the calling agent cannot see it.

Same three solver bodies. Same dictionary. The seam moved.

That trade is the whole folder:

    02   three tools  ->  the agent's model routes  ->  visible in the trace
    02b  one tool     ->  the SERVER routes         ->  invisible to the agent

Neither is "correct". One puts intelligence in the client and shows its work;
the other puts it in the server and gives every client — including a client
with no model at all — a single obvious door. Note what you lose: the agent
can no longer be blamed for a misroute, because it never made one.

Run it directly, in its own terminal:

    python mcp_server.py          # http on 127.0.0.1:8020

Never print to stdout in here. stdout IS the stdio protocol channel; one stray
print corrupts the JSON-RPC stream and the client dies with a parse error.
Diagnostics go to stderr, records go to SQLite.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

# Load ANTHROPIC_API_KEY from .env.local at the repo root (see shared/envloader.py).
# The SERVER needs the key here — that is new, and it is the point. In 02 only
# the agents talked to Claude; this server is itself a model client.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from envloader import load_env, require  # noqa: E402

load_env()

HERE = Path(__file__).parent
WORDLIST = HERE.parent / "shared" / "data" / "enable1.txt"
DB_PATH = HERE / "usage.db"

CLASSIFIER_MODEL = "claude-sonnet-5"


# --------------------------------------------------------------------------
# The word list, loaded ONCE at import time — unchanged from 02.
# --------------------------------------------------------------------------

def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


_t0 = time.perf_counter()
WORDS = load_words()
_load_ms = (time.perf_counter() - _t0) * 1000
print(
    f"[solo] loaded {len(WORDS):,} words from {WORDLIST.name} in {_load_ms:.1f}ms",
    file=sys.stderr,
)


# --------------------------------------------------------------------------
# Solver bodies — copied VERBATIM from shared/solvers_reference.py, exactly as
# in 00, 01 and 02. Four folders now, one implementation. Diff them.
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
# The classifier — the actual new thing in this folder.
#
# A JSON Schema plus one Claude call. `output_config.format` constrains the
# response to the schema, so this returns parseable JSON or it errors; there
# is no "sometimes the model wrapped it in a code fence" branch to write. That
# guarantee is why the classifier can live inside a server tool at all.
# --------------------------------------------------------------------------

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "game": {
            "type": "string",
            "enum": ["spelling_bee", "crossword", "wordle", "unknown"],
        },
        "letters": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "center": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "pattern": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "guesses": {
            "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
        },
        "feedback": {
            "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
        },
        "why": {"type": "string"},
    },
    "required": ["game", "letters", "center", "pattern", "guesses", "feedback", "why"],
    "additionalProperties": False,
}

CLASSIFIER_PROMPT = """\
You route word-puzzle requests. Read the text and return which game it is, plus
that game's arguments, extracted into the schema.

Decide from the SHAPE of the input. A descriptor may or may not be present; when
one is, honour it, and when it is absent, infer:

- seven letters plus a centre/middle/mandatory letter -> "spelling_bee".
  Set letters (the 7 letters) and center (one letter). Leave the rest null.
- letters interleaved with unknowns -> "crossword". Set pattern, normalising
  every unknown to a single underscore: dots, dashes, question marks, "blank",
  and "?" all become "_". Leave the rest null.
- one or more 5-letter guesses described with colours or a g/y/b string ->
  "wordle". Set guesses and feedback as parallel arrays, one feedback string
  per guess. Leave the rest null.
- anything else -> "unknown", and say what is missing in `why`.

feedback strings must be EXACTLY the letters g, y and b, one character per
letter of the guess. Translate colour words yourself: green->g, yellow->y,
grey/gray/black->b. "green, yellow, then three blacks" is "gybbb". Never return
colour words, and never return a feedback string of the wrong length.

Uppercase letters, center, pattern and guesses. `why` is one short sentence
naming the evidence you routed on.
"""

_client = anthropic.Anthropic()


def classify(puzzle: str) -> dict:
    """Ask Claude which game this is, and pull the arguments out of the text.

    Returns the validated schema object. Raises ToolError on a refusal, so a
    safety stop surfaces as a tool failure rather than a KeyError three frames
    later.
    """
    response = _client.messages.create(
        model=CLASSIFIER_MODEL,
        max_tokens=1024,
        system=CLASSIFIER_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": ROUTE_SCHEMA}},
        messages=[{"role": "user", "content": puzzle}],
    )
    # Check stop_reason before reading content: a refusal returns HTTP 200 with
    # an empty content list, and indexing it blind is the classic crash here.
    if response.stop_reason == "refusal":
        raise ToolError("the classifier declined to route this input")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise ToolError(f"classifier returned no text (stop_reason={response.stop_reason})")
    return json.loads(text)


# --------------------------------------------------------------------------
# The audit table. One extra column versus 02: `game`, the route the server
# chose. That column is the reason to centralize routing — every decision the
# server made is now queryable, including the wrong ones.
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS invocations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT    NOT NULL,   -- ISO8601 UTC
  agent_name  TEXT    NOT NULL,
  puzzle      TEXT    NOT NULL,   -- the raw text the caller sent
  game        TEXT    NOT NULL,   -- what the SERVER decided it was
  why         TEXT    NOT NULL,   -- the classifier's own stated reason
  outputs     TEXT    NOT NULL,   -- JSON
  route_ms    INTEGER NOT NULL,   -- time spent classifying
  solve_ms    INTEGER NOT NULL,   -- time spent solving
  ok          INTEGER NOT NULL    -- 1 success, 0 error
);
"""

COLUMNS = ["id", "ts", "agent_name", "puzzle", "game", "why", "outputs",
           "route_ms", "solve_ms", "ok"]

_db_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


with _db_lock, _connect() as _conn:
    _conn.executescript(SCHEMA)


def _record(agent_name: str, puzzle: str, game: str, why: str, outputs: str,
            route_ms: int, solve_ms: int, ok: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO invocations (ts, agent_name, puzzle, game, why, outputs,"
            " route_ms, solve_ms, ok) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
             agent_name, puzzle, game, why, outputs, route_ms, solve_ms, ok),
        )


def _json(value: object, limit: int = 8000) -> str:
    """Serialize for the audit column, truncating pathological payloads."""
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = json.dumps(str(value))
    if len(text) > limit:
        text = json.dumps({"truncated_chars": len(text), "preview": text[:limit]})
    return text


class RoutingLogMiddleware(Middleware):
    """Catch what the tool could not log itself.

    Unlike 02, the tool here does its own logging — it is the only place that
    knows which game was chosen, so an outer middleware cannot write that
    column. Middleware still earns its place for failures raised BEFORE the
    tool body records anything: a bad argument rejected by the schema, or the
    classifier itself erroring out. Those would otherwise leave no row at all.

    `_solo_logged` is how the two halves stay out of each other's way. Without
    it every solver failure writes twice — once here, once in the tool — and
    the audit trail double-counts exactly the rows you most want to trust.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        started = time.perf_counter()
        try:
            return await call_next(context)
        except Exception as exc:
            if getattr(exc, "_solo_logged", False):
                raise  # the tool already wrote a row, with the real game name
            args = dict(getattr(context.message, "arguments", None) or {})
            _record(
                str(args.get("agent_name") or "(unknown)"),
                str(args.get("puzzle") or ""), "(failed)", type(exc).__name__,
                _json({"error": str(exc)}),
                int((time.perf_counter() - started) * 1000), 0, 0,
            )
            print(f"[solo] ERR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            raise


mcp = FastMCP("puzzlemaster-solo")
mcp.add_middleware(RoutingLogMiddleware())


# --------------------------------------------------------------------------
# ONE tool. The entire public surface of this server.
# --------------------------------------------------------------------------

@mcp.tool(name="solve_puzzle")
def solve_puzzle_tool(agent_name: str, puzzle: str) -> dict:
    """Solve any word puzzle described in plain English.

    Args:
        agent_name: The name of the calling agent, e.g. "agent-solo".
        puzzle: The puzzle exactly as the user described it, verbatim. Do not
            reformat it, do not extract arguments, and do not name the game --
            the server works all of that out. Examples: "today's bee is VALIDTY,
            V in the middle", "what fits C_O__W_RD?", "CRANE gave me green,
            yellow, then three blacks".

    Returns the detected game, the arguments the server extracted, and the
    solution.
    """
    if not puzzle or not puzzle.strip():
        raise ToolError("puzzle must not be empty")

    t0 = time.perf_counter()
    route = classify(puzzle)
    route_ms = int((time.perf_counter() - t0) * 1000)
    game, why = route["game"], route["why"]

    t1 = time.perf_counter()
    try:
        if game == "spelling_bee":
            result = solve_spelling_bee(route["letters"] or "", route["center"] or "", WORDS)
        elif game == "crossword":
            result = solve_crossword_pattern(route["pattern"] or "", WORDS)
        elif game == "wordle":
            result = solve_wordle(route["guesses"] or [], route["feedback"] or [], WORDS)
        else:
            raise ValueError(f"could not tell which puzzle this is — {why}")
    except (ValueError, TypeError) as exc:
        solve_ms = int((time.perf_counter() - t1) * 1000)
        _record(agent_name, puzzle, game, why, _json({"error": str(exc)}),
                route_ms, solve_ms, 0)
        print(f"[solo] ERR {agent_name:14} {game:13} {exc}", file=sys.stderr, flush=True)
        error = ToolError(str(exc))
        error._solo_logged = True  # tell the middleware not to write a second row
        raise error from exc

    solve_ms = int((time.perf_counter() - t1) * 1000)
    payload = {"game": game, "why": why, "arguments": {
        k: route[k] for k in ("letters", "center", "pattern", "guesses", "feedback")
        if route[k] is not None
    }, "result": result}

    _record(agent_name, puzzle, game, why, _json(payload), route_ms, solve_ms, 1)
    # One readable line per call, to stderr. The room watches this window and
    # sees the server decide — which is the thing 02's trace showed on the
    # client side and this folder deliberately hides from the client.
    print(f"[solo] ok  {agent_name:14} {game:13} route {route_ms:>4}ms  "
          f"solve {solve_ms:>4}ms  <- {puzzle[:48]!r}",
          file=sys.stderr, flush=True)
    return payload


@mcp.tool
def routing_log(agent_name: str, limit: int = 20) -> str:
    """Show what the server decided, and why — the routing audit trail.

    Args:
        agent_name: The name of the calling agent, e.g. "monitor".
        limit: How many recent rows to show. Defaults to 20.

    Read this after a session to check the server's routing. A misroute is a
    server bug here, not an agent bug -- that shift in blame is the folder's
    argument, made checkable.
    """
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT ts, agent_name, game, ok, route_ms, puzzle, why"
            " FROM invocations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    if not rows:
        return "No invocations logged yet. Run agent_solo.py, then ask again."

    lines = [f"Last {len(rows)} routing decision(s)", ""]
    for ts, who, game, ok, ms, puzzle, why in rows:
        mark = "ok " if ok else "ERR"
        lines.append(f"{mark} {game:13} {ms:>4}ms  {puzzle[:44]!r}")
        lines.append(f"      -> {why}")
    return "\n".join(lines)


if __name__ == "__main__":
    # Run this in its OWN terminal. The agent does not start it.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--stdio", action="store_true",
                        help="serve over stdio instead (what a client would spawn)")
    args = parser.parse_args()

    # Fail loudly at startup, not on the first tool call: unlike every other
    # server in this repo, THIS one needs the key.
    require("ANTHROPIC_API_KEY")

    if args.stdio:
        mcp.run()
    else:
        print(f"[solo] classifier model: {CLASSIFIER_MODEL}", file=sys.stderr)
        print(f"[solo] listening on http://{args.host}:{args.port}/mcp", file=sys.stderr)
        mcp.run(transport="http", host=args.host, port=args.port,
                show_banner=False,
                uvicorn_config={"access_log": False})
