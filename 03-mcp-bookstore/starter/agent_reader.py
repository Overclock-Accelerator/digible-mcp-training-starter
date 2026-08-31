"""RightBookAI, the shop-floor concierge — YOUR WORK GOES HERE.

This is the client half of checkpoint A. It does nothing yet.

What must be true when you are done:

  * It connects to the bookstore MCP server you started in another terminal —
    it does NOT start one. Two processes, over HTTP.
  * It loads only the server's read tools. Not "is told not to write": the
    write tools must never be in the list it hands the model, so they are
    never in the model's schema at all. That absence is the demo.
  * Run with no arguments it opens a conversation; run with arguments it
    answers once and exits. See `shared/repl.py`.
  * Every turn prints the tools it invoked before the answer, via
    `shared/toolvis.py` — which `shared/repl.py` already does for you.
  * The API key comes from `.env.local` through `shared/envloader.py`, never
    from a shell export. Verify with:
        env -u ANTHROPIC_API_KEY python agent_reader.py "Do you have Dune?"
  * MCP tools are coroutine-only, so the whole entrypoint is async.

Compare with `rightbookai_agent.py` next door when you are done. That one
imports its tools; this one connects to them.

The brief, including prompts you can hand to a coding agent, is in
../README.md. `test_exercise.py` in this folder is the specification.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _shared_dir() -> Path:
    """Find the repo's shared/ directory by walking up, not by counting levels."""
    for d in Path(__file__).resolve().parents:
        if (d / "shared" / "envloader.py").is_file():
            return d / "shared"
    raise SystemExit(
        "could not find shared/envloader.py. Run this from inside the mcp-training "
        "repo, or copy the repo's shared/ directory into your own clone."
    )


sys.path.insert(0, str(_shared_dir()))

HERE = Path(__file__).resolve().parent
SERVER_URL = "http://127.0.0.1:8003/mcp"


if __name__ == "__main__":
    raise SystemExit(
        "agent_reader.py is not built yet.\n"
        "  It is checkpoint A's client half. The brief is in ../README.md.\n"
        "  Build the server first — python test_exercise.py -c A — then come\n"
        "  back here and connect to it at " + SERVER_URL + "."
    )
