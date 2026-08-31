"""One agent, connected to a growing set of MCP servers.

    ./start_servers.sh                              # first, in another terminal
    python agent.py                                 # chat, all five vendors, 155 tools
    python agent.py --servers 1                     # chat, Northwind only, 5 tools
    python agent.py --ask "find the rate limit docs" # one question, then exit
    python agent.py --task i_spaces --servers 5     # one scored task, then exit
    python agent.py --probe --servers 5             # the no-tool tax probe

**No arguments opens a conversation.** That is the repo convention, and here it
is also the best demo in the folder: run it with `--servers 1`, ask something
genuinely ambiguous, then run it again with `--servers 5` and ask the same
thing. Watch the tool-call line. A table of accuracy numbers is an assertion;
this is the thing itself, and it lets the room supply the ambiguous request.

**The chat loop is for demonstration, never for measurement.** Every number in
`results/` comes from `benchmark.py`, which drives `run()` below directly and
never touches this CLI.

The agent never changes. The model never changes. The prompts never change. The
only variable is how many vendors' servers are plugged in, which is exactly the
decision a platform team makes when someone says "we should hook up the CRM one
too, it's free".

The five servers are **separate long-running processes over HTTP**. This agent
connects to them by URL and never spawns them, so a room can watch a call land
in one vendor's window while the conversation happens here. Start them with
`./start_servers.sh`.

`MultiServerMCPClient.get_tools()` flattens every connected server into one flat
list of tools, which is also what the model sees: a single undifferentiated menu
with no vendor grouping and no hint that two entries do nearly the same thing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from catalog import PORTS, SERVERS, cumulative, tool_owner, url_for
from metrics import RunMetrics, collect
from tasks import TASKS, TAX_PROBE

HERE = Path(__file__).resolve().parent

# Repo convention: the key comes from .env.local, never a shell export.
sys.path.insert(0, str(HERE.parent / "shared"))
from envloader import load_env, require  # noqa: E402
from toolvis import show_tools  # noqa: E402
import repl  # noqa: E402

load_env()

MODEL = "anthropic:claude-sonnet-5"
AGENT_NAME = "ops-assistant"

# Deliberately says nothing about which vendor owns what. Everything the model
# needs to disambiguate is in the tool descriptions — which is the situation you
# are in the moment you connect a server somebody else configured.
SYSTEM_PROMPT = (
    "You are an operations assistant. Answer the user's request using the "
    "connected tools. Choose the single most appropriate tool for the system the "
    f'user is asking about. Pass agent_name="{AGENT_NAME}" on every tool call. '
    "Answer concisely."
)

OWNERS = tool_owner()


def connections(step: int, reverse: bool = False, host: str = "127.0.0.1") -> dict:
    """Server configs for the first `step` vendors, by URL.

    `reverse` flips the adoption order so Northwind — which owns every correct
    answer — is registered *last* instead of first. Tool position in a flat list
    is a known selection bias, so this is the control: if accuracy holds with the
    right answers buried at the bottom of 155 entries, position was not doing the
    work. Dict insertion order is what the adapter walks, so reversing here is
    what actually reorders the tool list the model sees.
    """
    keys = cumulative(step)
    if reverse:
        keys = list(reversed(keys))
    return {key: {"transport": "streamable_http", "url": url_for(key, host)}
            for key in keys}


async def connect(step: int, reverse: bool = False, host: str = "127.0.0.1") -> list:
    """Fetch the tool list, or exit explaining that the servers are not running.

    The agent does not spawn servers, so "connection refused" is a normal thing
    to hit once — and a stack trace is a bad way to learn that you skipped a
    step. Name the port that failed and the command that fixes it.
    """
    keys = cumulative(step)
    if reverse:
        keys = list(reversed(keys))
    try:
        return await MultiServerMCPClient(connections(step, reverse, host)).get_tools()
    except Exception as exc:
        wanted = "\n".join(f"    {SERVERS[k]['label']:<18} {url_for(k, host)}"
                            for k in keys)
        raise SystemExit(
            f"error: could not reach the MCP servers.\n"
            f"  ({type(exc).__name__}: {exc})\n\n"
            f"  This agent connects to servers you start yourself; it does not "
            f"spawn them.\n  Expected, on ports {PORTS[keys[0]]}-{PORTS[keys[-1]]}:\n"
            f"{wanted}\n\n"
            f"  Start them in another terminal:\n"
            f"    ./start_servers.sh\n"
        ) from None


async def run(task: str | None, step: int, probe: bool = False,
              reverse: bool = False) -> RunMetrics:
    """Run one task with the first `step` servers connected."""
    require("ANTHROPIC_API_KEY")
    prompt = TAX_PROBE["prompt"] if probe else TASKS[task]["prompt"]
    expected = "" if probe else TASKS[task]["correct"]

    started = time.perf_counter()
    # One flat list, every vendor mixed together — no namespacing, no grouping.
    tools = await connect(step, reverse)
    agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)
    # ainvoke, not invoke: MCP tools arrive as coroutine-only StructuredTools.
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

    m = collect(result["messages"], expected, OWNERS)
    m.wall_ms = int((time.perf_counter() - started) * 1000)
    return m


async def chat_session(step: int, reverse: bool = False) -> int:
    """Open a conversation against the first `step` vendors.

    The client and agent are built once and the history carries across turns, so
    a follow-up like "and who edited it last?" costs another full tool block —
    which is the entire point, and visible in the token line after each turn.
    """
    require("ANTHROPIC_API_KEY")
    tools = await connect(step, reverse)
    agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)

    labels = [SERVERS[k]["label"] for k in cumulative(step)]
    order = " (reversed — Northwind registered last)" if reverse else ""
    title = f"{step} server(s) · {len(tools)} tools · {', '.join(labels)}{order}"
    hints = [
        "ask for something ambiguous: \"find me the docs on rate limits\"",
        "then run again with --servers 1 and ask the identical thing",
        "watch the tool-call line: which tool, and whose server",
    ]
    return await repl.chat(agent, title=title, hints=hints)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chat with an agent wired to N vendors' MCP servers.")
    parser.add_argument("--task", choices=sorted(TASKS),
                        help="run one scored benchmark task once, then exit")
    parser.add_argument("--ask", metavar="TEXT",
                        help="ask one free-form question once, then exit")
    parser.add_argument("--servers", type=int, default=5, choices=range(1, 6),
                        help="how many vendors to connect, in adoption order")
    parser.add_argument("--probe", action="store_true",
                        help="run the no-tool tax probe instead of a task")
    parser.add_argument("--reverse", action="store_true",
                        help="register Northwind last — the tool-position control")
    args = parser.parse_args()

    connected = ", ".join(SERVERS[k]["label"] for k in cumulative(args.servers))
    n_tools = sum(len(SERVERS[k]["tools"]) for k in cumulative(args.servers))

    # A free-form question has no scored answer, so it goes through repl.once
    # rather than the metric path — nothing here should look like a measurement.
    if repl.one_shot(args, "ask"):
        require("ANTHROPIC_API_KEY")
        tools = await connect(args.servers, args.reverse)
        agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)
        print(f"\n{args.servers} server(s) · {n_tools} tools · {connected}")
        print(await repl.once(agent, args.ask))
        return 0

    # No task and no probe: the repo default, a conversation.
    if not (args.probe or repl.one_shot(args, "task")):
        return await chat_session(args.servers, args.reverse)

    m = await run(None if args.probe else args.task, args.servers,
                  probe=args.probe, reverse=args.reverse)
    # Rendered after the clock stopped, so printing never lands in wall_ms.
    show_tools(m.messages, f"{args.servers} servers · {n_tools} tools · {connected}")
    print(m.final_text)
    verdict = ("probe" if args.probe else
               ("correct" if m.correct else
                f"WRONG — picked {m.first_tool or '(none)'} from {m.first_server}"))
    print(f"\n[{args.servers} servers / {n_tools} tools] in={m.input_tokens} "
          f"out={m.output_tokens} round_trips={m.llm_calls} tool_calls={m.tool_calls} "
          f"wall={m.wall_ms}ms {verdict}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(repl.run(main()))
