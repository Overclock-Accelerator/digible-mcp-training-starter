"""The MCP arm: an agent whose capability arrives as typed MCP tools.

    python agent_mcp.py --task solve
    python agent_mcp.py --task undocumented --tools 40

Structurally matched to `agent_cli.py` — same model, same task prompts, same
metric collection, same async entrypoint. The single difference is the seam:
here the model sees three (or 15, or 40) tool schemas; there it sees one bash
tool and has to find things out for itself.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from metrics import RunMetrics, collect
from tasks import TASKS

HERE = Path(__file__).resolve().parent
SERVER = HERE / "mcp_server.py"

# Repo convention: the key comes from .env.local, never a shell export.
sys.path.insert(0, str(HERE.parent / "shared"))
from envloader import load_env, require  # noqa: E402
from toolvis import show_tools  # noqa: E402

# Anchored to this file, not the cwd: load_env() defaults to walking up from
# Path.cwd(), which finds nothing when the agent is run from outside the repo.
load_env(HERE)

MODEL = "anthropic:claude-sonnet-5"
AGENT_NAME = "agent-mcp"

# Deliberately says nothing about *which* puzzles are solvable. The tool schemas
# already carry that — being self-describing is MCP's actual advantage, and
# spelling it out in prose here would hand that advantage to the CLI arm too.
SYSTEM_PROMPT = (
    "You are a word-puzzle assistant. Use the tools to answer; never guess words "
    f'yourself. Pass agent_name="{AGENT_NAME}" on every tool call. Answer concisely.'
)


async def run(task: str, tool_count: int = 3) -> RunMetrics:
    """Run one task through the MCP agent and return what it cost."""
    require("ANTHROPIC_API_KEY")
    spec = TASKS[task]
    client = MultiServerMCPClient({
        "puzzlebench": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(SERVER), "--tools", str(tool_count)],
        },
    })

    started = time.perf_counter()
    # One session for the whole run: the server subprocess starts once, so the
    # 172k-word dictionary is loaded once no matter how many tool calls happen.
    async with client.session("puzzlebench") as session:
        tools = await load_mcp_tools(session)
        agent = create_agent(model=MODEL, tools=tools, system_prompt=SYSTEM_PROMPT)
        # ainvoke, not invoke: MCP tools arrive as coroutine-only StructuredTools.
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": spec["prompt"]}]}
        )

    m = collect(result["messages"], spec["expect"])
    m.wall_ms = int((time.perf_counter() - started) * 1000)
    return m


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run one benchmark task via MCP tools.")
    parser.add_argument("--task", choices=sorted(TASKS), default="solve")
    parser.add_argument("--tools", type=int, default=3,
                        help="how many tools the server exposes: 3 real + pad (default 3)")
    args = parser.parse_args()

    m = await run(args.task, args.tools)
    # Rendered after the clock stopped, so printing never lands in wall_ms.
    show_tools(m.messages, f"mcp — {args.tools} tools in context")
    print(m.final_text)
    print(f"\n[mcp/{args.task}/{args.tools} tools] in={m.input_tokens} out={m.output_tokens} "
          f"llm_calls={m.llm_calls} tool_calls={m.tool_calls} "
          f"tool_result_chars={m.tool_result_chars} wall={m.wall_ms}ms correct={m.correct}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
