#!/usr/bin/env python3
"""The same Spelling Bee solver, now behind a FastMCP server.

Run it directly (`python mcp_server.py`) and it speaks MCP over stdio.
agent_with_mcp.py launches this file as a subprocess; so can Claude Desktop,
Claude Code, the MCP Inspector, or a colleague's agent in any language.

STDOUT IS THE PROTOCOL CHANNEL. A single stray `print()` corrupts the JSON-RPC
stream and the connection dies. Every diagnostic in this file goes to stderr --
that is what the `stream=sys.stderr` below is buying.
"""

from __future__ import annotations

import logging
import argparse
import sys
from pathlib import Path

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bee")

mcp = FastMCP("spelling-bee")

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
# The seam. Compare with agent_with_tool.py: only the decorator differs.
# ==========================================================================

@mcp.tool
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
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--stdio", action="store_true",
                        help="serve over stdio instead (what a client would spawn)")
    args = parser.parse_args()

    if args.stdio:
        mcp.run()
    else:
        print(f"[bee] listening on http://{args.host}:{args.port}/mcp",
              file=sys.stderr)
        mcp.run(transport="http", host=args.host, port=args.port,
                show_banner=False,
                # Without this, four "POST /mcp 200 OK" lines per call bury
                # the tool-call lines the room is meant to be watching.
                # Setting the uvicorn.access logger level does not work --
                # uvicorn re-applies its own log config at startup.
                uvicorn_config={"access_log": False})
