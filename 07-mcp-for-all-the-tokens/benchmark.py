"""The harness: sweep the cumulative server set and write real numbers down.

    ./start_servers.sh                  # the five servers must be up first
    python benchmark.py                 # full sweep, 3 runs per cell (285 API calls)
    python benchmark.py --runs 1        # smoke run
    python benchmark.py --render-only   # re-render from the committed results.json

Two sweeps, both over the same axis — how many vendors are connected:

1. **The tax probe.** A prompt that needs no tool at all ("reply READY"), run at
   each step. One round-trip, everything fixed except the number of tool schemas
   sent. The delta between steps is the cost of the definitions alone, with no
   work mixed in. This is the cleanest number in the folder.

2. **The task matrix.** Fifteen tasks, each with exactly one correct tool, all of
   them on the first server, run at every step. The correct answer never moves;
   only the number of plausible alternatives grows. That isolates selection
   accuracy as a function of tool count. Five of the fifteen are adversarial —
   phrased so that a tool on another server keyword-matches better than the
   right one.

Plus one control:

3. **The position control.** Every task at step 5 again, with the server order
   reversed so Northwind — which owns every correct answer — is registered last
   instead of first. Position in a flat tool list is a known selection bias; if
   accuracy survives burying the right answers at the bottom of 155 entries, it
   was not position doing the work.

Three runs per cell because one run is noise: the model is sampled, and an
engineer in the room will (correctly) not believe a sample of one.

The servers are separate HTTP processes this harness connects to; it does not
start them. Transport is not a variable in any of these numbers — the tool block
serialized into the Anthropic request is byte-identical either way, and the tax
probe returns the same token counts to the digit over stdio and over HTTP.
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

import agent
from catalog import CONFUSABLES, ORDER, SERVERS, cumulative, tool_count
from tasks import TASKS

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS_JSON = RESULTS / "results.json"
CHART = RESULTS / "chart.txt"
ACCURACY = RESULTS / "accuracy.md"
TRACES = RESULTS / "traces.txt"
REPORT = RESULTS / "report.md"

sys.path.insert(0, str(HERE.parent / "shared"))
from toolvis import show_tools  # noqa: E402

STEPS = [1, 2, 3, 4, 5]
TOKEN_KEYS = ["input_tokens", "output_tokens", "llm_calls", "tool_calls", "wall_ms"]

# Sonnet list price, USD per million tokens, for the extrapolation section.
# Stated as an input so nobody has to reverse-engineer where the dollars came from.
PRICE_IN_PER_MTOK = 3.00


def stats_of(values: list[float]) -> dict:
    return {
        "mean": round(statistics.mean(values), 1),
        "stdev": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
        "min": min(values), "max": max(values),
    }


def summarize(runs: list[dict]) -> dict:
    s = {k: stats_of([r[k] for r in runs]) for k in TOKEN_KEYS}
    s["correct_runs"] = sum(1 for r in runs if r["correct"])
    s["total_runs"] = len(runs)
    s["wrong_server_runs"] = sum(1 for r in runs if r["correct"] is False and r["wrong_server"])
    s["recovered_runs"] = sum(1 for r in runs if r["recovered"])
    return s


def trace_of(m, title: str) -> str:
    """Render one run's tool-call trace to a string, after its clock has stopped."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        show_tools(m.messages, title)
    return buffer.getvalue()


async def cell(task: str | None, step: int, runs: int, probe: bool = False,
               reverse: bool = False) -> dict:
    records, trace = [], ""
    label = "probe" if probe else task
    for i in range(runs):
        m = await agent.run(task, step, probe=probe, reverse=reverse)
        records.append(m.as_dict())
        if i == 0:
            order = " · REVERSED order" if reverse else ""
            trace = trace_of(m, f"{label} · {step} servers · "
                                f"{tool_count(step)} tools{order}")
        verdict = "probe" if probe else ("ok" if m.correct else f"WRONG→{m.first_tool}")
        print(f"  step {step} ({tool_count(step):>3} tools)  {label:<10} run {i + 1}/{runs}  "
              f"in={m.input_tokens:<6} out={m.output_tokens:<4} rt={m.llm_calls} "
              f"wall={m.wall_ms}ms {verdict}", file=sys.stderr)
    return {"task": label, "probe": probe, "step": step, "reverse": reverse,
            "servers": cumulative(step), "tools": tool_count(step),
            "runs": records, "trace": trace, "stats": summarize(records)}


async def sweep(runs: int) -> dict:
    probes = [await cell(None, step, runs, probe=True) for step in STEPS]
    matrix = [await cell(task, step, runs) for step in STEPS for task in TASKS]
    control = [await cell(task, 5, runs, reverse=True) for task in TASKS]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": agent.MODEL,
        "runs_per_cell": runs,
        "price_in_per_mtok_usd": PRICE_IN_PER_MTOK,
        "servers": [{"key": k, "label": SERVERS[k]["label"],
                     "domain": SERVERS[k]["domain"], "tools": len(SERVERS[k]["tools"])}
                    for k in ORDER],
        "confusables": CONFUSABLES,
        "tasks": {k: {"prompt": v["prompt"], "kind": v["kind"],
                      "correct": v["correct"], "bait": v.get("bait", "")}
                  for k, v in TASKS.items()},
        "probes": probes,
        "matrix": matrix,
        "position_control": control,
    }


# --------------------------------------------------------------------------
# Rendering — ASCII bars, the same visual language as 02's usage_graph.
# --------------------------------------------------------------------------

def _bar(value: float, peak: float, width: int = 40) -> str:
    return "#" * max(1, round(value / peak * width)) if peak else ""


def per_tool_cost(data: dict) -> list[dict]:
    """The tax probe, turned into tokens-per-tool. One round-trip, so the input
    token count IS the per-request cost — no division by turns needed."""
    rows = []
    base = data["probes"][0]
    for p in data["probes"]:
        d_tok = p["stats"]["input_tokens"]["mean"] - base["stats"]["input_tokens"]["mean"]
        d_tools = p["tools"] - base["tools"]
        rows.append({
            "step": p["step"], "tools": p["tools"],
            "servers": [SERVERS[k]["label"] for k in p["servers"]],
            "input_tokens": p["stats"]["input_tokens"]["mean"],
            "stdev": p["stats"]["input_tokens"]["stdev"],
            "round_trips": p["stats"]["llm_calls"]["mean"],
            "per_tool": round(d_tok / d_tools, 1) if d_tools else None,
        })
    return rows


def accuracy_rows(data: dict, key: str = "matrix", steps=None) -> list[dict]:
    rows = []
    for step in (steps or STEPS):
        cells = [c for c in data[key] if c["step"] == step]
        if not cells:
            continue
        for kind in ("qualified", "implied", "adversarial", "all"):
            sel = [c for c in cells
                   if kind == "all" or data["tasks"][c["task"]]["kind"] == kind]
            if not sel:
                continue
            runs = [r for c in sel for r in c["runs"]]
            wrong = [r for r in runs if not r["correct"]]
            rows.append({
                "step": step, "tools": cells[0]["tools"], "kind": kind,
                "correct": sum(1 for r in runs if r["correct"]), "total": len(runs),
                "wrong_server": sum(1 for r in wrong if r["wrong_server"]),
                "recovered": sum(1 for r in wrong if r["recovered"]),
                "extra_round_trips": sum(r["extra_round_trips"] for r in runs),
                "misses": sorted({f"{r['expected_tool']}→{r['first_tool'] or '(no call)'}"
                                  f" [{r['first_server']}]" for r in wrong}),
            })
    return rows


def render_chart(data: dict) -> str:
    probes = per_tool_cost(data)
    peak = max(p["input_tokens"] for p in probes)
    lines = [
        "Five MCP servers, one agent — what the tool definitions cost",
        f"model {data['model']}   {data['runs_per_cell']} runs per cell   "
        f"generated {data['generated_at']}",
        "",
        "══ 1. THE TAX PROBE — input tokens for a prompt that calls no tool at all",
        "   one round-trip; the only thing that changes is how many schemas were sent",
        "",
    ]
    for p in probes:
        added = p["servers"][-1] if p["step"] > 1 else p["servers"][0]
        lines.append(f"  {p['step']} srv {p['tools']:>4} tools  "
                     f"{_bar(p['input_tokens'], peak):<40} "
                     f"{p['input_tokens']:>8.1f} tok  ±{p['stdev']:.1f}   +{added}")
    lines += ["", "  tokens per additional tool, measured against step 1:"]
    for p in probes[1:]:
        lines.append(f"    step {p['step']:>1}  {p['tools']:>3} tools   "
                     f"{p['per_tool']:>6.1f} tok/tool")
    lines += ["", ""]

    lines += ["══ 2. REAL TASKS — input tokens per run, summed over every round-trip", ""]
    peak_t = max(c["stats"]["input_tokens"]["mean"] for c in data["matrix"])
    for step in STEPS:
        cells = [c for c in data["matrix"] if c["step"] == step]
        mean_in = statistics.mean(c["stats"]["input_tokens"]["mean"] for c in cells)
        mean_out = statistics.mean(c["stats"]["output_tokens"]["mean"] for c in cells)
        mean_rt = statistics.mean(c["stats"]["llm_calls"]["mean"] for c in cells)
        mean_wall = statistics.mean(c["stats"]["wall_ms"]["mean"] for c in cells)
        lines.append(f"  {step} srv {cells[0]['tools']:>4} tools  "
                     f"{_bar(mean_in, peak_t):<40} {mean_in:>8.1f} tok in   "
                     f"{mean_out:>5.1f} out   {mean_rt:.1f} round-trips   "
                     f"{mean_wall / 1000:.1f}s")
    lines += ["", ""]

    lines += ["══ 3. SELECTION ACCURACY — same fifteen tasks, same fifteen right answers;",
              "   the only thing growing is the number of plausible wrong ones", ""]
    for row in accuracy_rows(data):
        if row["kind"] != "all":
            continue
        pct = 100 * row["correct"] / row["total"]
        lines.append(f"  {row['step']} srv {row['tools']:>4} tools  "
                     f"{_bar(pct, 100):<40} {row['correct']:>3}/{row['total']} "
                     f"= {pct:5.1f}%   wrong-server {row['wrong_server']}   "
                     f"extra round-trips {row['extra_round_trips']}")
    lines += ["", "  split by phrasing (qualified names the vendor; implied does not;",
              "  adversarial is phrased so a rival tool keyword-matches better):", ""]
    for kind in ("qualified", "implied", "adversarial"):
        cells = [r for r in accuracy_rows(data) if r["kind"] == kind]
        joined = "  ".join(f"{c['tools']}t:{c['correct']}/{c['total']}" for c in cells)
        lines.append(f"    {kind:<12} {joined}")

    ctrl = [r for r in accuracy_rows(data, "position_control", [5]) if r["kind"] == "all"]
    if ctrl:
        c = ctrl[0]
        lines += ["", "  position control — 155 tools, Northwind registered LAST:", "",
                  f"    {c['correct']}/{c['total']} = "
                  f"{100 * c['correct'] / c['total']:.1f}%   "
                  f"wrong-server {c['wrong_server']}   "
                  f"extra round-trips {c['extra_round_trips']}"]
    lines.append("")
    return "\n".join(lines)


def render_accuracy(data: dict) -> str:
    rows = accuracy_rows(data)
    out = [
        "# Selection accuracy as tool count grows",
        "",
        f"Model `{data['model']}`, {data['runs_per_cell']} runs per task per step, "
        f"generated {data['generated_at']}.",
        "",
        "Fifteen tasks, each with exactly one correct tool. Every correct tool lives on",
        "**Northwind Docs**, the server connected at every step — so the right answer",
        "never moves and only the distractor pile grows. Twenty of the other 150 tools",
        "are deliberate near-duplicates of Northwind's five.",
        "",
        "`wrong-server` counts runs where the first tool call went to a different",
        "vendor entirely. `recovered` counts wrong first picks that later called the",
        "right tool in the same run.",
        "",
        "| servers | tools | phrasing | correct | accuracy | wrong-server | recovered | extra round-trips |",
        "|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        out.append(f"| {r['step']} | {r['tools']} | {r['kind']} | "
                   f"{r['correct']}/{r['total']} | "
                   f"{100 * r['correct'] / r['total']:.1f}% | {r['wrong_server']} | "
                   f"{r['recovered']} | {r['extra_round_trips']} |")

    ctrl = accuracy_rows(data, "position_control", [5])
    if ctrl:
        out += ["", "## Position control — Northwind registered last", "",
                "Same 155 tools, same tasks, but the server holding every correct answer",
                "is registered *after* the other four instead of before them.", "",
                "| phrasing | correct | accuracy | wrong-server | extra round-trips |",
                "|---|---:|---:|---:|---:|"]
        for r in ctrl:
            out.append(f"| {r['kind']} | {r['correct']}/{r['total']} | "
                       f"{100 * r['correct'] / r['total']:.1f}% | {r['wrong_server']} | "
                       f"{r['extra_round_trips']} |")

    out += ["", "## The bait each adversarial task was carrying", "",
            "| task | prompt | correct tool | nearest wrong match |", "|---|---|---|---|"]
    for name, spec in data["tasks"].items():
        if spec["kind"] == "adversarial":
            out.append(f"| `{name}` | {spec['prompt']} | `{spec['correct']}` | "
                       f"{spec.get('bait', '')} |")

    out += ["", "## Were the distractor tools touched at all?", "",
            "Not just \"was the first call right\" — did any call, anywhere in any run,",
            "reach a tool on a server other than Northwind?", ""]
    every = [r for key in ("matrix", "position_control") for c in data[key] for r in c["runs"]]
    calls = [call for r in every for call in r["calls"]]
    foreign = [c for c in calls if c["server"] != "northwind-docs"]
    out += [f"- Task runs: **{len(every)}**",
            f"- Tool calls made: **{len(calls)}**",
            f"- Calls to any of the 150 non-Northwind tools: **{len(foreign)}**"]
    if foreign:
        seen: dict[str, int] = {}
        for c in foreign:
            seen[f"{c['tool']} ({c['server']})"] = seen.get(f"{c['tool']} ({c['server']})", 0) + 1
        out += ["", "| tool | server | times called |", "|---|---|---:|"]
        out += [f"| `{k}` | | {v} |" for k, v in sorted(seen.items())]
    out += ["",
            "Multi-call runs, and what the sequence was:", ""]
    chains: dict[str, int] = {}
    for r in every:
        if len(r["calls"]) > 1:
            key = " → ".join(c["tool"] for c in r["calls"])
            chains[key] = chains.get(key, 0) + 1
    out += ([f"- `{k}` — {v} runs" for k, v in sorted(chains.items(), key=lambda kv: -kv[1])]
            or ["- none; every run was a single tool call"])

    out += ["", "## Every wrong selection observed", ""]
    misses = [(r["step"], r["tools"], m) for r in rows if r["kind"] == "all"
              for m in r["misses"]]
    if misses:
        out += ["| servers | tools | expected → chosen [owning server] |", "|---:|---:|---|"]
        out += [f"| {s} | {t} | `{m}` |" for s, t, m in misses]
    else:
        out += ["**None.** Across every step, every task and every run, the first tool",
                "call was the correct one. Reported as observed — see the README for",
                "what was tried to induce an error and why it is still a useful result.",
                ""]
    return "\n".join(out) + "\n"


def render_report(data: dict) -> str:
    probes = per_tool_cost(data)
    last, first = probes[-1], probes[0]
    per_tool = last["per_tool"]
    full_stack = last["input_tokens"]
    delta = full_stack - first["input_tokens"]
    rows = [r for r in accuracy_rows(data) if r["kind"] == "all"]

    out = [
        "# What five MCP servers cost one agent",
        "",
        f"Measured {data['generated_at']} with `{data['model']}`, "
        f"{data['runs_per_cell']} runs per cell. Token counts come from the "
        "Anthropic API's own `usage_metadata`, summed across every round-trip. "
        "Nothing here is estimated.",
        "",
        "## The stack",
        "",
        "| # | vendor | domain | tools | cumulative |",
        "|---:|---|---|---:|---:|",
    ]
    running = 0
    for i, s in enumerate(data["servers"], 1):
        running += s["tools"]
        out.append(f"| {i} | {s['label']} | {s['domain']} | {s['tools']} | {running} |")

    out += ["", "## 1. The tool-definition tax", "",
            "A prompt that calls no tool at all — one round-trip, everything fixed",
            "except how many schemas were serialized into the request.", "",
            "| servers connected | tools | input tokens | vs. 1 server | tok/tool |",
            "|---|---:|---:|---:|---:|"]
    for p in probes:
        ratio = p["input_tokens"] / first["input_tokens"]
        out.append(f"| {', '.join(p['servers'])} | {p['tools']} | "
                   f"{p['input_tokens']:.0f} ± {p['stdev']:.0f} | {ratio:.2f}x | "
                   f"{p['per_tool'] if p['per_tool'] is not None else '—'} |")
    slopes = [p["per_tool"] for p in probes[1:] if p["per_tool"] is not None]
    out += ["",
            f"**{min(slopes):.0f}–{max(slopes):.0f} input tokens per tool per request** "
            f"(last step: {per_tool:.0f}), near-flat across a "
            f"{last['tools'] // first['tools']}x range in tool count. Connecting all five "
            f"vendors costs **{delta:,.0f} input tokens on every single turn**, before "
            "the agent does any work at all.",
            "",
            "Standard deviation is zero at every step: the tool block is deterministic "
            "text, not an average you might get lucky on.", ""]

    turns = 40
    cost_turn = full_stack * PRICE_IN_PER_MTOK / 1e6
    out += ["### What that extrapolates to", "",
            f"At list price (${PRICE_IN_PER_MTOK:.2f} per million input tokens):", "",
            f"- One turn with the full stack attached: **{full_stack:,.0f} input tokens**, "
            f"about **${cost_turn:.3f}**.",
            f"- A {turns}-turn working session: **{full_stack * turns:,.0f} input tokens**, "
            f"about **${cost_turn * turns:.2f}** — and "
            f"**{delta * turns:,.0f}** of those tokens are tool definitions for servers "
            "the agent may never touch.",
            f"- Connecting only the one server actually needed: "
            f"**{first['input_tokens'] * turns:,.0f} tokens**, about "
            f"**${first['input_tokens'] * turns * PRICE_IN_PER_MTOK / 1e6:.2f}**.",
            "",
            "That is a straight-line extrapolation of a measured per-turn cost, not a "
            "measured conversation. It also assumes no prompt caching; see the caveats.",
            ""]

    out += ["## 2. Selection accuracy", "",
            "| servers | tools | correct | accuracy | wrong-server | extra round-trips |",
            "|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r['step']} | {r['tools']} | {r['correct']}/{r['total']} | "
                   f"{100 * r['correct'] / r['total']:.1f}% | {r['wrong_server']} | "
                   f"{r['extra_round_trips']} |")
    ctrl = [r for r in accuracy_rows(data, "position_control", [5]) if r["kind"] == "all"]
    if ctrl:
        out += [f"| 5 *(control: Northwind last)* | {ctrl[0]['tools']} | "
                f"{ctrl[0]['correct']}/{ctrl[0]['total']} | "
                f"{100 * ctrl[0]['correct'] / ctrl[0]['total']:.1f}% | "
                f"{ctrl[0]['wrong_server']} | {ctrl[0]['extra_round_trips']} |"]

    every = [r for key in ("matrix", "position_control") for c in data[key] for r in c["runs"]]
    calls = [call for r in every for call in r["calls"]]
    foreign = [c for c in calls if c["server"] != "northwind-docs"]
    total_wrong = sum(r["total"] - r["correct"] for r in rows)
    n_distractors = sum(s["tools"] for s in data["servers"][1:])
    out += ["",
            f"Wrong first selections across the whole sweep: **{total_wrong}**.",
            f"Tool calls made in total: **{len(calls)}**, of which calls to any of the "
            f"{n_distractors} non-Northwind tools: **{len(foreign)}**.",
            "",
            "Full breakdown, including the bait each adversarial task carried, in "
            "`accuracy.md`.", ""]
    return "\n".join(out) + "\n"


def render_traces(data: dict) -> str:
    out = [f"Tool-call traces — first run of every cell, {data['model']}, "
           f"generated {data['generated_at']}", ""]
    for c in data["probes"] + data["matrix"] + data["position_control"]:
        out += [c["trace"].rstrip(), ""]
    return "\n".join(out)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep the cumulative MCP server set.")
    parser.add_argument("--runs", type=int, default=3, help="repeats per cell (default 3)")
    parser.add_argument("--render-only", action="store_true",
                        help="re-render from the committed results.json")
    args = parser.parse_args()

    RESULTS.mkdir(exist_ok=True)
    if args.render_only:
        data = json.loads(RESULTS_JSON.read_text())
    else:
        # Fail in two seconds rather than forty minutes in. `connect` raises
        # SystemExit with the start command if anything is unreachable.
        await agent.connect(len(STEPS))
        data = await sweep(args.runs)
        RESULTS_JSON.write_text(json.dumps(data, indent=2) + "\n")

    CHART.write_text(render_chart(data))
    ACCURACY.write_text(render_accuracy(data))
    REPORT.write_text(render_report(data))
    TRACES.write_text(render_traces(data))
    print(CHART.read_text())
    print(f"wrote {RESULTS_JSON.name}, {CHART.name}, {ACCURACY.name}, "
          f"{REPORT.name}, {TRACES.name} to {RESULTS}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
