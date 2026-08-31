"""Print what the model actually receives for a tool — and what the whole block weighs.

    python show_schema.py                       # one schema, verbatim
    python show_schema.py --tool find_documents
    python show_schema.py --servers 5 --weigh   # every schema, total characters

No API key needed: this talks to the MCP servers, not to the model.

The point of `--weigh` is to make the tax tangible before anyone sees a token
count. The tool block is not metadata the client keeps to itself; it is text
serialized into the request body, every request, for the life of the
conversation. `--weigh` prints how many characters of it there are.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent import connections  # noqa: E402
from catalog import SERVERS, cumulative, tool_owner  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the tool block the model sees.")
    parser.add_argument("--tool", default="search_docs")
    parser.add_argument("--servers", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--weigh", action="store_true",
                        help="print the size of the whole tool block instead of one schema")
    args = parser.parse_args()

    tools = await MultiServerMCPClient(connections(args.servers)).get_tools()
    owners = tool_owner()

    if not args.weigh:
        match = [t for t in tools if t.name == args.tool]
        if not match:
            raise SystemExit(f"no tool named {args.tool!r} on the first "
                             f"{args.servers} server(s)")
        t = match[0]
        print(json.dumps({"name": t.name, "description": t.description,
                          "inputSchema": t.args_schema}, indent=2))
        return 0

    total = 0
    per_server: dict[str, int] = {}
    for t in tools:
        size = len(json.dumps({"name": t.name, "description": t.description,
                               "inputSchema": t.args_schema}))
        total += size
        per_server[owners.get(t.name, "?")] = per_server.get(owners.get(t.name, "?"), 0) + size

    for key in cumulative(args.servers):
        print(f"  {SERVERS[key]['label']:<18} {len(SERVERS[key]['tools']):>3} tools   "
              f"{per_server.get(key, 0):>7,} chars")
    print(f"  {'TOTAL':<18} {len(tools):>3} tools   {total:>7,} chars")
    print("\n  That block is serialized into every request, whether or not the "
          "model calls anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
