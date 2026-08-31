"""LangBookStore behind one MCP server — YOUR WORK GOES HERE.

Right now this file exposes nothing. That is deliberate: the exercise is to
decide what it should expose, and the interesting decisions are all in that
choice. `test_exercise.py` is the specification — run it, read what it wants,
and build until it is satisfied.

    python test_exercise.py          # the whole contract
    python test_exercise.py -c A     # one checkpoint at a time

What must be true when you are done:

  * This module defines `mcp`, a FastMCP server, and the tools live on it.
  * Read tools take TYPED parameters, not a customer's sentence, and return
    STRUCTURED data, not prose. Read `tools/get_answers.py` first to see what
    you are getting rid of, and `inventory.py` to see what you are keeping.
  * Write tools persist to `storedata.json` and are visible to reads made
    afterwards, in the same process.
  * The write path requires a credential the model cannot see, cannot set,
    and cannot spoof — it must not appear in any tool's input schema.
  * Nothing in this file ever prints to stdout. Under stdio transport stdout
    IS the JSON-RPC channel, and one stray print kills the client. Diagnostics
    go to stderr; that is what the `file=sys.stderr` below is for.

The server is a separate process. You start it; no agent starts it for you.

    python bookstore_server.py              # http://127.0.0.1:8003/mcp
    python bookstore_server.py --stdio      # what a client would spawn instead

See ../README.md for the full brief, including prompts you can hand to a
coding agent. `test_exercise.py` in this folder is the specification.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from fastmcp import FastMCP

import inventory

mcp = FastMCP("bookstore")

print(
    f"[bookstore] catalog: {inventory.DATA_PATH} "
    f"({len(inventory.load_books())} books, {len(inventory.GENRES)} genres)",
    file=sys.stderr,
)

# Handy for a genre parameter's description — the model should never have to
# guess how this store spells "Science Fiction".
_GENRE_HELP = "One of: " + ", ".join(inventory.GENRES)

# The names each agent will be allowed to load. The reader's list is what makes
# the refusal demo work: a tool that is not on it never reaches the model.
READ_TOOLS = ("search_books", "get_book", "recommend_books", "build_bundle")
WRITE_TOOLS = ("add_book", "update_book", "delete_book")


# ==========================================================================
# Your tools go here.
# ==========================================================================


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--stdio", action="store_true",
                        help="serve over stdio instead (what a client would spawn)")
    args = parser.parse_args()

    if not asyncio.run(mcp.list_tools()):
        raise SystemExit(
            "This server exposes no tools yet, so nothing could connect to it.\n"
            "  Start with checkpoint A:  python test_exercise.py -c A\n"
            "  The brief is in ../README.md."
        )

    if args.stdio:
        mcp.run()
    else:
        # Leave this running in its own terminal, then start an agent in
        # another one. Two processes is the point — you can watch each tool
        # call arrive here while the conversation happens over there.
        print(f"[bookstore] listening on http://{args.host}:{args.port}/mcp",
              file=sys.stderr)
        mcp.run(transport="http", host=args.host, port=args.port)
