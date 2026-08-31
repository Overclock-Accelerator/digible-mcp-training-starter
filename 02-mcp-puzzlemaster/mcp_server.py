"""PuzzleMaster — one MCP server, three agents, one audit trail.

The ONE idea: once several agents share a single MCP server, you get things you
cannot get from tools scattered across three codebases — one dictionary loaded
once, one place that sees every call, and one table you can graph and export.

Run it directly for a smoke test:

    python mcp_server.py          # stdio transport, blocks

Never print to stdout in here. stdout IS the stdio protocol channel; one stray
print corrupts the JSON-RPC stream and the client dies with a parse error.
Diagnostics go to stderr, records go to SQLite.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import argparse
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

HERE = Path(__file__).parent
WORDLIST = HERE.parent / "shared" / "data" / "enable1.txt"
DB_PATH = HERE / "usage.db"

# --------------------------------------------------------------------------
# The word list, loaded ONCE at import time.
#
# This is the centralization argument made concrete. In 00 every agent process
# holds its own copy of a 172k-word dictionary; three agents means three copies
# that can silently drift apart. Here there is exactly one, in one process, and
# the load cost is paid once for the life of the server instead of once per
# call.
# --------------------------------------------------------------------------

def load_words(path: Path = WORDLIST) -> list[str]:
    """Load the ENABLE1 word list, uppercased."""
    return [w.strip().upper() for w in path.read_text().splitlines() if w.strip()]


_t0 = time.perf_counter()
WORDS = load_words()
_load_ms = (time.perf_counter() - _t0) * 1000
print(
    f"[puzzlemaster] loaded {len(WORDS):,} words from {WORDLIST.name} "
    f"in {_load_ms:.1f}ms — once, for every agent",
    file=sys.stderr,
)


# --------------------------------------------------------------------------
# Solver bodies — copied VERBATIM from shared/solvers_reference.py.
#
# Do not "improve" them here. The whole lesson of 00 -> 01 -> 02 is that the
# solving code is byte-identical and only the seam around it changes, so these
# must stay diffable against the reference module. The @mcp.tool wrappers below
# are that seam: they add agent identity, hand in the shared WORDS list, and
# translate ValueError into ToolError.
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
# The audit table
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS invocations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT    NOT NULL,   -- ISO8601 UTC
  agent_name TEXT    NOT NULL,
  tool       TEXT    NOT NULL,   -- the "purpose"
  inputs     TEXT    NOT NULL,   -- JSON
  outputs    TEXT    NOT NULL,   -- JSON
  duration_ms INTEGER NOT NULL,
  ok         INTEGER NOT NULL    -- 1 success, 0 error
);
"""

COLUMNS = ["id", "ts", "agent_name", "tool", "inputs", "outputs", "duration_ms", "ok"]

_db_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db() -> None:
    with _db_lock, _connect() as conn:
        conn.executescript(SCHEMA)


def _record(agent_name: str, tool: str, inputs: str, outputs: str,
            duration_ms: int, ok: int) -> None:
    """Append one row. A connection per write — writes are rare and tiny, and
    this sidesteps sharing a connection across the event loop's threads."""
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO invocations (ts, agent_name, tool, inputs, outputs, duration_ms, ok)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
             agent_name, tool, inputs, outputs, duration_ms, ok),
        )


_init_db()


# --------------------------------------------------------------------------
# Logging middleware.
#
# Middleware, not a per-tool decorator, because `on_call_tool` is the ONE seam
# every tool call already crosses: it sees the tool name, the raw arguments,
# the result, the exception, and the timing, without a single line inside any
# solver. Add a sixth tool tomorrow and it is audited for free. That is the
# point the folder is making — centralizing created a place to stand.
# --------------------------------------------------------------------------

def _watch(agent_name: str, tool: str, args: dict, ok: bool, ms: int) -> None:
    """One readable line per call, to stderr.

    The server runs in its own terminal so the room can watch invocations
    arrive while the conversation happens next door. That only works if this
    window stays quiet enough to read -- which is also why uvicorn's access
    log is switched off at startup.
    """
    shown = ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:3])
    mark = "ok " if ok else "ERR"
    print(f"[puzzlemaster] {mark} {agent_name:16} {tool}({shown})  {ms}ms",
          file=sys.stderr, flush=True)


def _json(value: object, limit: int = 8000) -> str:
    """Serialize for the audit column, truncating pathological payloads.

    A 34-word answer is small; a one-letter crossword pattern matches thousands
    of words and would otherwise bloat the table.
    """
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = json.dumps(str(value))
    if len(text) > limit:
        # Stay valid JSON so the audit column is always machine-readable.
        text = json.dumps({"truncated_chars": len(text), "preview": text[:limit]})
    return text


class UsageLoggingMiddleware(Middleware):
    """Write one `invocations` row per tool call — successes AND failures.

    An audit trail that only records what worked is not an audit trail. Errors
    land with ok=0 and the exception message in `outputs`, which is exactly the
    signal you want when an agent is quietly failing in a loop.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        args = dict(getattr(context.message, "arguments", None) or {})
        tool = context.message.name
        # agent_name is an ordinary tool parameter, so it arrives in `args`.
        # It is telemetry, not authentication — see the README.
        agent_name = str(args.pop("agent_name", None) or "(unknown)")
        started = time.perf_counter()

        try:
            result = await call_next(context)
        except Exception as exc:
            _record(
                agent_name, tool, _json(args),
                _json({"error": type(exc).__name__, "message": str(exc)}),
                int((time.perf_counter() - started) * 1000), 0,
            )
            _watch(agent_name, tool, args, False,
                   int((time.perf_counter() - started) * 1000))
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        payload = result.structured_content
        if payload is None:
            payload = [getattr(c, "text", str(c)) for c in (result.content or [])]
        _record(agent_name, tool, _json(args), _json(payload),
                duration_ms, 0 if result.is_error else 1)
        _watch(agent_name, tool, args, not result.is_error, duration_ms)
        return result


mcp = FastMCP("puzzlemaster")
mcp.add_middleware(UsageLoggingMiddleware())


# --------------------------------------------------------------------------
# Tools. Every one takes an explicit agent_name so the audit trail can answer
# "who called this?" — see the README on why that is honest telemetry and not
# authentication.
# --------------------------------------------------------------------------

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


@mcp.tool
def usage_graph(agent_name: str, group_by: str = "agent") -> str:
    """Render an ASCII bar chart of logged tool usage.

    Args:
        agent_name: The name of the calling agent, e.g. "monitor".
        group_by: "agent" to chart calls per agent, "tool" for calls per tool.

    Reads the same SQLite table every call is written to, so it reflects all
    agents, across restarts.
    """
    if group_by not in ("agent", "tool"):
        raise ToolError('group_by must be "agent" or "tool"')

    column = "agent_name" if group_by == "agent" else "tool"
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            f"SELECT {column}, COUNT(*), SUM(ok), SUM(duration_ms)"
            " FROM invocations GROUP BY 1 ORDER BY 2 DESC, 1"
        ).fetchall()

    if not rows:
        return "No invocations logged yet. Run an agent, then ask again."

    total = sum(r[1] for r in rows)
    peak = max(r[1] for r in rows)
    width = max(len(str(r[0])) for r in rows)
    lines = [
        f"Tool usage by {group_by} — {total} invocation(s), {len(rows)} {group_by}(s)",
        "",
    ]
    for label, count, oks, ms in rows:
        bar = "#" * max(1, round(count / peak * 40))
        failed = count - (oks or 0)
        note = f"{count:>4}  avg {int((ms or 0) / count):>5}ms"
        if failed:
            note += f"  ({failed} failed)"
        lines.append(f"{str(label):<{width}}  {bar:<40} {note}")
    return "\n".join(lines)


@mcp.tool
def export_results(agent_name: str, path: str) -> str:
    """Export every logged invocation to CSV and return the file path.

    Args:
        agent_name: The name of the calling agent, e.g. "monitor".
        path: Where to write the CSV, e.g. "results.csv".

    The CSV is an audit trail AND a ready-made eval dataset: every row is an
    input/output pair nobody had to write by hand.
    """
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM invocations ORDER BY id"
        ).fetchall()

    out = Path(path).expanduser()
    if not out.is_absolute():
        out = HERE / out
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
    except OSError as exc:
        raise ToolError(f"could not write {out}: {exc}") from exc

    print(f"[puzzlemaster] exported {len(rows)} rows to {out}", file=sys.stderr)
    return str(out)


if __name__ == "__main__":
    # Run this in its OWN terminal. The agent does not start it.
    #
    #     python mcp_server.py            # here, and leave it running
    #     python agent_with_mcp.py        # over there, in a second terminal
    #
    # Two processes, talking over HTTP. You can watch each tool call arrive
    # in this window while the conversation happens in the other one -- which
    # is the whole point, and what stdio auto-spawning hides.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--stdio", action="store_true",
                        help="serve over stdio instead (what a client would spawn)")
    args = parser.parse_args()

    if args.stdio:
        mcp.run()
    else:
        print(f"[puzzlemaster] listening on http://{args.host}:{args.port}/mcp",
              file=sys.stderr)
        mcp.run(transport="http", host=args.host, port=args.port,
                show_banner=False,
                # Without this, four "POST /mcp 200 OK" lines per call bury
                # the tool-call lines the room is meant to be watching.
                # Setting the uvicorn.access logger level does not work --
                # uvicorn re-applies its own log config at startup.
                uvicorn_config={"access_log": False})
