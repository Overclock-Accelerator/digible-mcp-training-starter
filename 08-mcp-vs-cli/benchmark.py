"""The harness: run the task matrix N times per cell and write real numbers down.

    python benchmark.py                    # full run, 5 repeats, writes results/
    python benchmark.py --runs 2           # faster smoke run
    python benchmark.py --render-only      # re-render charts from results.json

Two sweeps:

1. **The matrix** — every task, both arms, N repeats. Input and output tokens
   are recorded separately because they price differently and because the whole
   MCP tax lands on the input side.
2. **The tool-count sweep** — the MCP arm running one fixed task at 3, 15 and 40
   tools. The CLI arm is flat at one tool definition by construction, which is
   the point.

N repeats because a single run is noise: the model is sampled, not deterministic,
and an engineer in the room will (correctly) not believe a sample of one.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import agent_cli
import agent_mcp
from tasks import TASKS

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS_JSON = RESULTS / "results.json"
CHART = RESULTS / "chart.txt"
SCALING = RESULTS / "tool_scaling.md"
TRACES = RESULTS / "traces.txt"
CATALOG = RESULTS / "cli_catalog.txt"

sys.path.insert(0, str(HERE.parent / "shared"))
from toolvis import show_tools  # noqa: E402

MODEL = agent_mcp.MODEL
# Both a briefed task and an unbriefed one, because the honest counter-cost of
# a big CLI catalogue is discovery, and discovery only shows up when the agent
# has to go looking.
SCALING_TASKS = ["solve", "undocumented"]
SCALING_COUNTS = [3, 15, 40]
METRIC_KEYS = ["input_tokens", "output_tokens", "total_tokens", "llm_calls",
               "tool_calls", "tool_result_chars", "wall_ms"]


def summarize(runs: list[dict]) -> dict:
    """Mean and spread per metric. Spread matters more than the mean here —
    a benchmark that reports only a mean is hiding how much it varied."""
    ok = [r for r in runs if r["correct"]]
    stats = {}
    for key in METRIC_KEYS:
        values = [r[key] for r in runs]
        stats[key] = {
            "mean": round(statistics.mean(values), 1),
            "stdev": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    stats["correct_runs"] = len(ok)
    stats["total_runs"] = len(runs)
    return stats


def trace_of(m, title: str) -> str:
    """Render one run's tool-call trace to a string.

    Called after the run's clock has stopped, so rendering never lands in
    wall_ms. A table of token counts is an assertion; this is the argument —
    the fat MCP result and the four-byte piped result, side by side.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        show_tools(m.messages, title)
    return buffer.getvalue()


async def cell(arm: str, task: str, capabilities: int, runs: int) -> dict:
    """One cell of the matrix: the same (arm, task, capabilities) run N times."""
    records, trace = [], ""
    for i in range(runs):
        if arm == "mcp":
            m = await agent_mcp.run(task, capabilities)
        else:
            m = await agent_cli.run(task, capabilities, briefed=arm == "cli+schema")
        records.append(m.as_dict())
        if i == 0:
            unit = "tools in context" if arm == "mcp" else "commands on disk"
            trace = trace_of(m, f"{arm} · {task} · {capabilities} {unit}")
        print(f"  {arm:<10} {task:<12} n={capabilities:<2} run {i + 1}/{runs}  "
              f"in={m.input_tokens:<6} out={m.output_tokens:<4} calls={m.llm_calls} "
              f"wall={m.wall_ms}ms {'ok' if m.correct else 'WRONG'}", file=sys.stderr)
    return {"arm": arm, "task": task, "capabilities": capabilities,
            "runs": records, "trace": trace, "stats": summarize(records)}


async def benchmark(runs: int) -> dict:
    matrix = []
    for task in TASKS:
        arms = ["mcp", "cli"]
        # The briefed CLI arm only exists where discovery and composition collide.
        if task == "aggregate":
            arms.append("cli+schema")
        for arm in arms:
            matrix.append(await cell(arm, task, 3, runs))

    scaling = []
    for task in SCALING_TASKS:
        for n in SCALING_COUNTS:
            # n=3 duplicates a matrix cell deliberately: the sweep should be one
            # continuous set of runs, not two halves stitched together.
            for arm in ("mcp", "cli"):
                scaling.append(await cell(arm, task, n, runs))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "runs_per_cell": runs,
        "scaling_tasks": SCALING_TASKS,
        "tasks": {k: {"prompt": v["prompt"], "measures": v["measures"]} for k, v in TASKS.items()},
        "matrix": matrix,
        "scaling": scaling,
    }


# --------------------------------------------------------------------------
# Rendering — ASCII bars, same visual language as 02's usage_graph.
# --------------------------------------------------------------------------

def _bar(value: float, peak: float, width: int = 40) -> str:
    return "#" * max(1, round(value / peak * width)) if peak else ""


def render_chart(data: dict) -> str:
    lines = [
        "MCP tools vs. CLI + bash — same solvers, same model, same prompts",
        f"model {data['model']}   {data['runs_per_cell']} runs per cell   "
        f"generated {data['generated_at']}",
        "",
    ]

    by_task: dict[str, dict[str, dict]] = {}
    for c in data["matrix"]:
        by_task.setdefault(c["task"], {})[c["arm"]] = c

    for task, arms in by_task.items():
        lines += [f"── {task}: {TASKS[task]['measures']}", ""]
        peak_in = max(a["stats"]["input_tokens"]["mean"] for a in arms.values())
        peak_out = max(a["stats"]["output_tokens"]["mean"] for a in arms.values())
        order = [a for a in ("mcp", "cli", "cli+schema") if a in arms]
        for metric, peak, unit in (("input_tokens", peak_in, "tok"),
                                   ("output_tokens", peak_out, "tok")):
            lines.append(f"  {metric}")
            for arm in order:
                s = arms[arm]["stats"][metric]
                lines.append(f"    {arm:<10} {_bar(s['mean'], peak):<40} "
                             f"{s['mean']:>8.1f} {unit}  ±{s['stdev']:.1f}  "
                             f"[{s['min']}–{s['max']}]")
            lines.append("")
        for arm in order:
            s = arms[arm]["stats"]
            lines.append(f"    {arm:<10} round-trips {s['llm_calls']['mean']:.1f}   "
                         f"tool calls {s['tool_calls']['mean']:.1f}   "
                         f"tool output {s['tool_result_chars']['mean']:.0f} chars   "
                         f"wall {s['wall_ms']['mean'] / 1000:.1f}s   "
                         f"correct {s['correct_runs']}/{s['total_runs']}")
        lines.append("")

    lines += ["", "══ capabilities in context vs. capabilities on disk", ""]
    for task in data["scaling_tasks"]:
        cells = [c for c in data["scaling"] if c["task"] == task]
        peak = max(c["stats"]["input_tokens"]["mean"] for c in cells)
        lines += [f"── input tokens vs. capability count — task: {task} "
                  f"({TASKS[task]['measures'].split(':')[0]})", ""]
        for arm in ("mcp", "cli"):
            for c in [c for c in cells if c["arm"] == arm]:
                s = c["stats"]["input_tokens"]
                unit = "tools" if arm == "mcp" else "cmds "
                lines.append(f"  {arm:<4}{c['capabilities']:>3} {unit} "
                             f"{_bar(s['mean'], peak):<40} {s['mean']:>8.1f} tok  "
                             f"±{s['stdev']:.1f}")
            lines.append("")
        lines.append("  the honest counter-cost — what a big catalogue does to the CLI:")
        for arm in ("mcp", "cli"):
            for c in [c for c in cells if c["arm"] == arm]:
                s = c["stats"]
                lines.append(f"    {arm:<4}{c['capabilities']:>3}  "
                             f"out {s['output_tokens']['mean']:>6.1f} tok "
                             f"±{s['output_tokens']['stdev']:.1f}   "
                             f"round-trips {s['llm_calls']['mean']:.1f}   "
                             f"tool calls {s['tool_calls']['mean']:.1f}   "
                             f"correct {s['correct_runs']}/{s['total_runs']}")
        lines.append("")
    return "\n".join(lines)


def render_scaling(data: dict) -> str:
    rows = [
        "# Capabilities in context vs. capabilities on disk",
        "",
        f"Model `{data['model']}`, {data['runs_per_cell']} runs per row, "
        f"generated {data['generated_at']}.",
        "",
        "Both arms are padded from the *same* 37-entry catalogue (`pad_catalog.py`), so",
        "\"40 tools\" and \"40 commands\" are the same 40 capabilities. MCP re-sends every",
        "tool's name, description and full JSON schema on every request; the CLI keeps",
        "them on disk and sends one `bash` definition regardless.",
        "",
        "Input tokens are summed across every round-trip in a run — the real bill, since",
        "the tool block is re-sent on each one. Output tokens and round-trips are listed",
        "separately because that is where a big CLI catalogue would show its own cost.",
        "",
    ]
    for task in data["scaling_tasks"]:
        cells = [c for c in data["scaling"] if c["task"] == task]
        briefed = "briefed" if task == "solve" else "NOT briefed — discovery required"
        rows += [f"## Task: `{task}` ({briefed})", "",
                 f"> {data['tasks'][task]['prompt']}", "",
                 "| interface | capabilities | input tok | vs. 3 | tok per extra cap. "
                 "| output tok | round-trips |", "|---|---:|---:|---:|---:|---:|---:|"]
        for arm, label in (("mcp", "MCP"), ("cli", "CLI + bash")):
            arm_cells = [c for c in cells if c["arm"] == arm]
            base = arm_cells[0]["stats"]["input_tokens"]["mean"]
            for c in arm_cells:
                s, o, r = (c["stats"]["input_tokens"], c["stats"]["output_tokens"],
                           c["stats"]["llm_calls"])
                extra = c["capabilities"] - arm_cells[0]["capabilities"]
                per = f"{(s['mean'] - base) / extra:.0f}" if extra else "—"
                rows.append(f"| {label} | {c['capabilities']} | {s['mean']:.0f} ± "
                            f"{s['stdev']:.0f} | {s['mean'] / base:.2f}x | {per} "
                            f"| {o['mean']:.0f} ± {o['stdev']:.0f} | {r['mean']:.1f} |")
        rows.append("")
    return "\n".join(rows)


def render_traces(data: dict) -> str:
    """One full tool-call trace per cell — the evidence behind the token counts."""
    out = [f"Tool-call traces — first run of every cell, {data['model']}, "
           f"generated {data['generated_at']}", "",
           "Rendered by shared/toolvis.py. It elides long arguments, so the verbatim",
           "command follows each trace — for the CLI arm the jq pipeline IS the finding,",
           "and an elided one would hide it.", ""]
    for c in data["matrix"] + data["scaling"]:
        out.append(c["trace"].rstrip())
        for i, action in enumerate(c["runs"][0]["actions"], 1):
            out.append(f"  [{i}] {action}")
        out.append("")
    return "\n".join(out)


def render_catalog() -> str:
    """`ls` of the PATH directory at each padding level.

    This is the flat line made concrete: 40 commands on disk, and not one byte
    of them in the context window.
    """
    out = ["What the CLI agent's PATH actually contains at each padding level.",
           "Generated from cli/pad/, which comes from the same pad_catalog.py the",
           "MCP server registers as tools.", ""]
    for n in SCALING_COUNTS:
        with agent_cli.capability_path(n) as bin_dir:
            names = sorted(p.name for p in bin_dir.iterdir())
        out += [f"$ ls $PATH_DIR   # {n} capabilities "
                f"({len(names)} command{'s' if len(names) != 1 else ''}: "
                f"puzzle + {len(names) - 1} pad)", ""]
        out += ["  " + "  ".join(names[i:i + 4]) for i in range(0, len(names), 4)]
        out.append("")
    out += ["The model never sees this listing unless it goes looking.",
            "The MCP arm sends the equivalent catalogue on every single request.", ""]
    return "\n".join(out)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark MCP tools against a CLI.")
    parser.add_argument("--runs", type=int, default=5, help="repeats per cell (default 5)")
    parser.add_argument("--render-only", action="store_true",
                        help="re-render charts from the committed results.json")
    args = parser.parse_args()

    RESULTS.mkdir(exist_ok=True)
    if args.render_only:
        data = json.loads(RESULTS_JSON.read_text())
    else:
        data = await benchmark(args.runs)
        RESULTS_JSON.write_text(json.dumps(data, indent=2) + "\n")

    CHART.write_text(render_chart(data))
    SCALING.write_text(render_scaling(data))
    TRACES.write_text(render_traces(data))
    CATALOG.write_text(render_catalog())
    print(CHART.read_text())
    print(f"wrote {RESULTS_JSON.name}, {CHART.name}, {SCALING.name}, "
          f"{TRACES.name}, {CATALOG.name} to {RESULTS}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
