"""One generic FastMCP server, instantiated five times with five catalogues.

    python servers/server.py --server northwind-docs       # HTTP on its own port
    python servers/server.py --server bastion-infra --stdio  # spawned-subprocess mode

Each server runs in **its own process**, over HTTP, and the agent connects to it
by URL. Five vendors means five processes — which is the honest shape of the
thing being demonstrated, and why `start_servers.sh` exists. Every tool call
prints in the window of the server that received it, so the room can watch
requests land on Bastion while the conversation happens somewhere else.

Five separate files would have been five copies of the same twenty lines. The
thing that differs between the vendors is the *catalogue*, and that lives in
`catalog.py`, so it is the only thing this script varies.

Tools are built from the catalogue with real signatures — the parameter names,
types and defaults are exec'd into an actual Python function so FastMCP derives
a genuine JSON schema from it. That matters: the whole folder measures what
schemas cost, and a hand-waved schema would measure the wrong thing.

The fixture world contains exactly one corpus: Northwind's pages. Every other
server answers honestly that it has no matching record, which is what a real
help-center search would say if you asked it for an internal runbook. That is
deliberate — it lets the harness see whether an agent that picked the wrong
vendor notices and recovers, or just reports the empty result as the answer.

Never print to stdout here. Under stdio transport stdout IS the protocol
channel; every log line goes to stderr.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from catalog import PORTS, SERVERS  # noqa: E402

# --------------------------------------------------------------------------
# Fixtures — the only real content in the world, all of it Northwind's.
# --------------------------------------------------------------------------

PAGES = {
    "NW-4471": {
        "title": "Database failover runbook",
        "space": "Engineering",
        "body": "# Database failover runbook\n\nPromote the healthiest replica, "
                "repoint the connection pool, then verify replication lag is under "
                "500ms before declaring the failover complete.",
        "history": [
            {"revision": 12, "author": "priya.raman", "at": "2026-08-19T14:02:00Z",
             "summary": "Add replication-lag verification step"},
            {"revision": 11, "author": "tom.oyelaran", "at": "2026-07-30T09:41:00Z",
             "summary": "Clarify connection-pool repointing"},
        ],
    },
    "NW-2210": {
        "title": "Blue-green deploy checklist",
        "space": "Engineering",
        "body": "# Blue-green deploy checklist\n\nCut traffic to green in 10% "
                "increments. Hold at 50% for one full metrics window before "
                "completing the cut.",
        "history": [
            {"revision": 7, "author": "dana.k", "at": "2026-08-24T11:15:00Z",
             "summary": "Hold at 50% for a full metrics window"},
            {"revision": 6, "author": "priya.raman", "at": "2026-06-02T16:20:00Z",
             "summary": "Initial checklist"},
        ],
    },
    "NW-0091": {
        "title": "On-call expectations",
        "space": "Engineering",
        "body": "# On-call expectations\n\nAcknowledge within 5 minutes. Escalate "
                "to the secondary after 15 minutes with no acknowledgement.",
        "history": [
            {"revision": 3, "author": "sam.iyer", "at": "2026-05-11T08:00:00Z",
             "summary": "Tighten escalation window to 15 minutes"},
        ],
    },
}

SPACES = ["Engineering", "Product", "Security", "Data Platform", "People Ops"]


def _northwind(name: str, args: dict) -> dict:
    """Real answers for the five Northwind tools."""
    if name == "search_docs":
        query = str(args.get("query", "")).lower()
        terms = [w for w in query.replace("-", " ").split() if len(w) > 3]
        hits = [
            {"doc_id": pid, "title": p["title"], "space": p["space"],
             "snippet": p["body"].splitlines()[2][:90]}
            for pid, p in PAGES.items()
            if any(term in (p["title"] + " " + p["body"]).lower() for term in terms)
        ]
        return {"system": "Northwind Docs", "results": hits or list(
            {"doc_id": pid, "title": p["title"], "space": p["space"]}
            for pid, p in PAGES.items())[:3], "result_count": len(hits)}
    if name == "get_doc":
        page = PAGES.get(str(args.get("doc_id", "")).upper())
        if not page:
            return {"system": "Northwind Docs", "error": "no such page"}
        return {"system": "Northwind Docs", "doc_id": args.get("doc_id"),
                "title": page["title"], "space": page["space"], "body": page["body"]}
    if name == "create_doc":
        return {"system": "Northwind Docs", "created": True, "doc_id": "NW-5502",
                "title": args.get("title"), "space": args.get("space"),
                "url": "https://northwind.internal/NW-5502"}
    if name == "list_spaces":
        return {"system": "Northwind Docs", "spaces": SPACES}
    if name == "get_doc_history":
        page = PAGES.get(str(args.get("doc_id", "")).upper())
        if not page:
            return {"system": "Northwind Docs", "error": "no such page"}
        return {"system": "Northwind Docs", "doc_id": args.get("doc_id"),
                "revisions": page["history"]}
    return {"system": "Northwind Docs", "ok": True}


def _empty(label: str, name: str) -> dict:
    """What the other four vendors honestly return: nothing matched.

    Not an error — an empty result. That is the realistic failure mode and the
    interesting one: an agent that mis-selects gets a plausible-looking
    zero-result payload rather than a red flag, and has to decide for itself
    that it asked the wrong system.
    """
    return {"system": label, "tool": name, "result_count": 0, "results": [],
            "note": f"No matching records in {label}."}


def build(server_key: str) -> FastMCP:
    spec = SERVERS[server_key]
    label = spec["label"]
    mcp = FastMCP(label)

    def respond(name: str, args: dict) -> str:
        caller = args.pop("agent_name", "unknown")
        print(f"[{label}] {caller} → {name}({json.dumps(args, default=str)[:120]})",
              file=sys.stderr, flush=True)
        payload = (_northwind(name, args) if server_key == "northwind-docs"
                   else _empty(label, name))
        return json.dumps(payload)

    namespace = {"_respond": respond}
    for name, sig, doc in spec["tools"]:
        params = f"agent_name: str, {sig}" if sig else "agent_name: str"
        exec(f"def {name}({params}) -> str:\n"
             f"    return _respond({name!r}, dict(locals()))\n", namespace)
        fn = namespace[name]
        fn.__doc__ = doc
        mcp.tool(fn)

    return mcp


def main() -> int:
    # Run this in its OWN terminal. The agent does not start it.
    #
    #     ./start_servers.sh              # all five, here
    #     python agent.py --servers 5     # over there, in another terminal
    #
    # Six processes talking over HTTP. Watching a call arrive in the Bastion
    # window while you type in the agent window is the part stdio auto-spawning
    # hides — and with five vendors connected, seeing *which* window lights up
    # is exactly the question this folder is about.
    parser = argparse.ArgumentParser(description="Run one vendor's MCP server.")
    parser.add_argument("--server", choices=sorted(SERVERS), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int,
                        help="defaults to this vendor's assigned port (8010-8014)")
    parser.add_argument("--stdio", action="store_true",
                        help="serve over stdio instead (what a client would spawn)")
    args = parser.parse_args()

    # The point of a server in its own window is watching tool calls arrive.
    # FastMCP's banner buries them, and so does uvicorn's access log — four
    # "POST /mcp 200 OK" lines per tool call, plus session setup and teardown.
    # Setting the logger level is not enough: uvicorn re-applies its own log
    # config when it starts, so the access log has to be switched off through
    # uvicorn_config instead.
    logging.getLogger("FastMCP").setLevel(logging.WARNING)
    mcp = build(args.server)

    if args.stdio:
        mcp.run(transport="stdio", show_banner=False)
        return 0

    port = args.port or PORTS[args.server]
    label = SERVERS[args.server]["label"]
    print(f"[{label}] {len(SERVERS[args.server]['tools'])} tools listening on "
          f"http://{args.host}:{port}/mcp", file=sys.stderr, flush=True)
    mcp.run(transport="http", host=args.host, port=port, show_banner=False,
            uvicorn_config={"access_log": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
