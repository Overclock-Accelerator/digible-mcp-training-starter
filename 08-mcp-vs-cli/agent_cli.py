"""The CLI arm: an agent whose capability arrives as one bash tool.

    python agent_cli.py --task solve

Structurally matched to `agent_mcp.py` — same model, same task prompts, same
metric collection, same async entrypoint. One tool definition, forever, no
matter how many commands live on the PATH. What the model must supply instead
is knowledge of what those commands are.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import contextvars
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool

from metrics import RunMetrics, collect
from pad_catalog import PAD_TOOLS
from tasks import TASKS

HERE = Path(__file__).resolve().parent
CLI_DIR = HERE / "cli"
PAD_DIR = CLI_DIR / "pad"

# Repo convention: the key comes from .env.local, never a shell export.
sys.path.insert(0, str(HERE.parent / "shared"))
from envloader import load_env, require  # noqa: E402
from toolvis import show_tools  # noqa: E402

# Anchored to this file, not the cwd: load_env() defaults to walking up from
# Path.cwd(), which finds nothing when the agent is run from outside the repo.
load_env(HERE)

MODEL = "anthropic:claude-sonnet-5"
REAL_CAPABILITIES = 3   # puzzle's three subcommands: bee, crossword, wordle
TIMEOUT_S = 60
MAX_OUTPUT_CHARS = 20_000

# Matched to agent_mcp.py's prompt: it names the entrypoint and gives one worked
# invocation, exactly as the MCP tool schemas do for their own tools. It does NOT
# enumerate subcommands — that is the discovery cost the "undocumented" task
# exists to measure, and pre-briefing it here would rig the result.
SYSTEM_PROMPT = (
    "You are a word-puzzle assistant with a bash tool. A `puzzle` command is on your "
    "PATH, and `jq` is available for processing its output. Use them to answer; never "
    "guess words yourself. Example: `puzzle bee --letters VALIDTY --center V --json`. "
    "Answer concisely."
)

# The optional third arm. MCP hands the model its output schema for free, in the
# tool definition; the CLI agent has to discover it. This one sentence is what
# that discovery buys, and running with and without it separates "composition is
# cheap" from "composition is cheap once you know the shape".
SCHEMA_BRIEF = (
    " `--json` emits {\"words\": [{\"word\", \"points\", \"pangram\"}], \"count\", "
    "\"total_points\", \"pangrams\"}."
)


# The PATH directory for the current run. A context variable rather than a
# global because it is per-run state that the bash tool has to see, and the tool
# is a module-level singleton shared across every run in a benchmark sweep.
_bin_dir: contextvars.ContextVar[Path] = contextvars.ContextVar("bin_dir", default=CLI_DIR)


@contextlib.contextmanager
def capability_path(capabilities: int):
    """Expose exactly `capabilities` commands on the PATH.

    `puzzle` provides the three real capabilities (bee, crossword, wordle); the
    rest are symlinked from cli/pad/, which is generated from the same
    pad_catalog table the MCP server registers as tools. So "40 tools" and "40
    commands" are the same 40 things, and the two lines share an x-axis.

    The whole point of this arm is that none of it reaches the model: adding
    the 37th command changes what is on disk, not what is in the context window.
    """
    pad = capabilities - REAL_CAPABILITIES
    if pad < 0:
        raise SystemExit(f"--capabilities must be at least {REAL_CAPABILITIES}")
    if pad > len(PAD_TOOLS):
        raise SystemExit(f"only {len(PAD_TOOLS)} pad commands exist, asked for {pad}")

    with tempfile.TemporaryDirectory(prefix="puzzlebench-bin-") as tmp:
        bin_dir = Path(tmp)
        (bin_dir / "puzzle").symlink_to(CLI_DIR / "puzzle.py")
        for name, _, _ in PAD_TOOLS[:pad]:
            command = name.replace("_", "-")
            (bin_dir / command).symlink_to(PAD_DIR / command)
        token = _bin_dir.set(bin_dir)
        try:
            yield bin_dir
        finally:
            _bin_dir.reset(token)


def _env() -> dict:
    env = dict(os.environ)
    # The run's capability directory comes first, so `puzzle` and the pad
    # commands resolve as bare command names; the venv follows it so the
    # scripts' `#!/usr/bin/env python3` shebang finds an interpreter.
    env["PATH"] = f"{_bin_dir.get()}:{Path(sys.executable).parent}:{env.get('PATH', '')}"
    return env


@tool
async def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr.

    Args:
        command: The command line to run, e.g. `puzzle --help`. Pipes,
            redirection and standard Unix tools are available.
    """
    def _run() -> str:
        try:
            p = subprocess.run(command, shell=True, capture_output=True, text=True,
                               timeout=TIMEOUT_S, env=_env(), cwd=str(HERE))
        except subprocess.TimeoutExpired:
            return f"(timed out after {TIMEOUT_S}s)"
        out = (p.stdout or "") + (p.stderr or "")
        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:MAX_OUTPUT_CHARS] + f"\n(truncated at {MAX_OUTPUT_CHARS} chars)"
        return out.strip() or f"(no output, exit status {p.returncode})"

    return await asyncio.to_thread(_run)


async def run(task: str, capabilities: int = REAL_CAPABILITIES,
              briefed: bool = False) -> RunMetrics:
    """Run one task through the CLI agent and return what it cost.

    `capabilities` is how many commands sit on the PATH — the CLI mirror of the
    MCP arm's `--tools`. It changes nothing the model is sent up front, which is
    the hypothesis this arm exists to test.

    `briefed=True` adds the output schema to the system prompt — the thing MCP
    gives the model for nothing.
    """
    require("ANTHROPIC_API_KEY")
    spec = TASKS[task]
    prompt = SYSTEM_PROMPT + (SCHEMA_BRIEF if briefed else "")
    agent = create_agent(model=MODEL, tools=[bash], system_prompt=prompt)

    with capability_path(capabilities):
        started = time.perf_counter()
        result = await agent.ainvoke({"messages": [{"role": "user", "content": spec["prompt"]}]})
        m = collect(result["messages"], spec["expect"])
        m.wall_ms = int((time.perf_counter() - started) * 1000)
    return m


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run one benchmark task via a CLI + bash tool.")
    parser.add_argument("--task", choices=sorted(TASKS), default="solve")
    parser.add_argument("--capabilities", type=int, default=REAL_CAPABILITIES,
                        help="how many commands to put on the PATH (default 3)")
    parser.add_argument("--brief", action="store_true",
                        help="tell the model the --json output schema up front")
    args = parser.parse_args()

    m = await run(args.task, args.capabilities, args.brief)
    # Rendered after the clock stopped, so printing never lands in wall_ms.
    show_tools(m.messages, f"cli — {args.capabilities} commands on disk")
    print(m.final_text)
    print(f"\n[cli{'+schema' if args.brief else ''}/{args.task}/{args.capabilities} cmds] in={m.input_tokens} out={m.output_tokens} "
          f"llm_calls={m.llm_calls} tool_calls={m.tool_calls} "
          f"tool_result_chars={m.tool_result_chars} wall={m.wall_ms}ms correct={m.correct}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
