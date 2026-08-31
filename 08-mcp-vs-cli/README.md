# 08 — MCP vs. CLI: the same solvers, measured

**The one idea:** MCP and a CLI are two seams over the same capability, and the seam you choose is a *per-request bill* — tool schemas are re-sent on every turn and scale with tool count, while a shell agent pays for one tool definition forever and can pipe intermediate results away before they ever enter the context window.

This folder is a benchmark, not an argument. Every number below was measured, not estimated: LangChain surfaces the Anthropic API's own `usage_metadata` on each AI message, and `metrics.py` sums it across the whole trajectory.

**Results generated 2026-08-31 (UTC) with `anthropic:claude-sonnet-5`, 5 runs per cell, 95 runs total, 95/95 correct.** Re-running will move the numbers a little; the shape holds.

Every run's tool calls are on screen and in [`results/traces.txt`](results/traces.txt) — a table of token counts is an assertion, a trace beside it is an argument.

## The experiment

The controlled experiment already existed in this repo. `shared/solvers_reference.py` holds three solver bodies. `02-mcp-puzzlemaster` wraps them in MCP tools. Here, `cli/puzzle` wraps the *same bodies* in argparse — so two interfaces sit over byte-identical logic and nothing differs except the seam.

That claim is checked, not asserted:

```bash
python verify_solvers.py
# cli/puzzle.py    solve_spelling_bee       identical  (1307 bytes)
# mcp_server.py    solve_spelling_bee       identical  (1307 bytes)
# ...
# OK — 4 solvers byte-identical across 2 implementations.
```

Both agents use the same model, the same task prompts, the same async entrypoint and the same metric collection. The MCP agent gets typed tools; the CLI agent gets one `bash` tool and a `puzzle` command on its PATH.

## Run it

Put your key in `.env.local` at the repo root — no shell export, and nothing to remember per terminal:

```bash
cp .env.local.example .env.local
$EDITOR .env.local          # ANTHROPIC_API_KEY=sk-ant-...
```

Both agents call `load_env()` from `shared/envloader.py`, which walks up to find `.env.local` and never overwrites an already-set variable, so an `export` still wins if you want one. Then, with the shared virtualenv active:

```bash
cd 08-mcp-vs-cli
python cli/make_pad.py                    # generate the 37 pad commands (no key needed)
python verify_solvers.py                  # no key needed
python benchmark.py --runs 5              # ~12 minutes, ~95 API calls
python benchmark.py --render-only         # re-render every artifact, free
```

Single runs, for poking at one cell. Each prints its tool calls before its answer:

```bash
python agent_mcp.py --task aggregate --tools 40
python agent_cli.py --task aggregate --capabilities 40 --brief
```

The CLI works on its own, with no model in the loop at all:

```bash
cli/puzzle bee --letters VALIDTY --center V --json | jq '.count, .total_points'
```

## Results

Full chart in [`results/chart.txt`](results/chart.txt); raw per-run records, including every command each agent issued, in [`results/results.json`](results/results.json).

### 1. Capabilities in context vs. capabilities on disk

The single most valuable chart in this folder, and the axis worth naming out loud. **MCP puts capabilities in the context window; a CLI puts them on disk.** MCP re-sends every tool's name, description and full JSON schema on *every request* — a fixed recurring tax on the whole catalogue, paid whether the model touches one tool or none. The CLI sends one `bash` definition regardless, and pays only when the model goes looking.

Both arms are padded from the **same 37-entry catalogue** (`pad_catalog.py`), registered as MCP tools by `mcp_server.py` and generated as executable scripts by `cli/make_pad.py`. So "40 tools" and "40 commands" are the same 40 capabilities, and the two lines genuinely share an x-axis. The pad entries are plausible word utilities (`find_anagrams`, `count_syllables`, `scrabble_score`, …) with real parameters, real docstrings and real `--help` text. **None of them are ever called by either arm.**

Task `solve`, both sides briefed:

| interface | capabilities | input tok (mean ± sd) | vs. 3 | tok per extra capability | output tok | round-trips |
|---|---:|---:|---:|---:|---:|---:|
| MCP | 3 | 3344 ± 12 | 1.00x | — | 167 ± 7 | 2.0 |
| MCP | 15 | 7629 ± 0 | 2.28x | **+357** | 168 ± 1 | 2.0 |
| MCP | 40 | 16320 ± 16 | **4.88x** | **+351** | 180 ± 16 | 2.0 |
| CLI + bash | 3 | 2220 ± 6 | 1.00x | — | 118 ± 14 | 2.0 |
| CLI + bash | 15 | 2220 ± 6 | **1.00x** | **0** | 111 ± 12 | 2.0 |
| CLI + bash | 40 | 2217 ± 0 | **1.00x** | **0** | 114 ± 13 | 2.0 |

**The MCP line is dead linear at ~355 input tokens per additional capability per run** — two round-trips, so ~178 tokens per tool per request. **The CLI line is flat to within measurement noise: 2220, 2220, 2217.** Adding 37 capabilities changed the CLI's input cost by 3 tokens, and one of those is rounding.

Thirty-seven tools nobody touched cost the MCP arm 12,976 input tokens. A 40-tool server is not 40 conveniences; it is a fixed ~6,500-token toll on every single turn. Attach three such servers and the model starts the conversation 20,000 tokens in the red.

The flat line is what `results/cli_catalog.txt` shows concretely — 38 commands sitting on the PATH:

```
$ ls $PATH_DIR   # 40 capabilities (38 commands: puzzle + 37 pad)

  acrostic-build  antonym-lookup  boggle-solve  caesar-shift
  check-spelling  clue-difficulty  contains-search  count-syllables
  ...
```

The model never sees that listing unless it goes looking. The MCP arm sends the equivalent catalogue on every request.

### 1b. The honest counter-cost, which did not appear

The expected trade is that a big CLI catalogue raises *discovery* cost: `ls`, then `--help`, then a retry after guessing a flag wrong — extra round-trips and extra output tokens on any task the agent was not briefed for. So the sweep was also run on `undocumented`, which neither system prompt mentions:

| interface | capabilities | input tok | output tok | round-trips |
|---|---:|---:|---:|---:|
| MCP | 3 | 2548 ± 0 | 112 ± 7 | 2.0 |
| MCP | 15 | 6844 ± 13 | 123 ± 18 | 2.0 |
| MCP | 40 | 15518 ± 0 | 121 ± 7 | 2.0 |
| CLI + bash | 3 | 2067 ± 1090 | 165 ± 122 | 2.6 |
| CLI + bash | 15 | 1392 ± 56 | 130 ± 56 | 2.0 |
| CLI + bash | 40 | 1572 ± 470 | 110 ± 23 | 2.2 |

**The predicted rise did not happen, and we are not going to pretend it did.** The CLI's discovery cost is real — look at the spread, ±1090 at three commands, driven by single runs that guessed a subcommand wrong and had to recover — but it does **not scale with catalogue size**. At 40 commands it is no worse than at 3.

The traces say why. Across all 30 CLI runs in the sweep, **not one ran `ls`.** The agent goes straight to `puzzle crossword --pattern ...`, usually hedged with `|| puzzle --help` in the same command. It never enumerates the directory, so the size of the directory never reaches it. Discovery cost here is a function of *how guessable the interface is*, not of how much is installed.

That is a real limit on the finding: a catalogue of 40 badly-named commands, or one where the agent had to enumerate before choosing, would likely behave differently. What is measured is that catalogue size alone does not move the CLI arm, while it moves the MCP arm 4.9x.

### 2. CLI composes; MCP returns whatever it returns

Task: *how many of the Spelling Bee answers are 5 or more letters long?* The answer is the integer 24.

| arm | input tok | output tok | round-trips | tool output into context |
|---|---:|---:|---:|---:|
| MCP | 3345 ± 0 | 428 ± 20 | 2.0 | **1,665 chars** |
| CLI (unbriefed) | 3926 ± 63 | 196 ± 49 | 3.2 | 1,609 chars |
| CLI (schema known) | **1449 ± 1** | **96 ± 1** | 2.0 | **2 chars** |

The two traces, side by side, are the whole argument — this is what `results/traces.txt` puts on screen:

```
──── mcp · aggregate · 3 tools in context ────────────────────────
  1. solve_spelling_bee(agent_name="agent-mcp", letters="VALIDTY", center="V")
     → [{'type': 'text', 'text': '{"words":[{"word":"VALIDITY","points":15,...

──── cli+schema · aggregate · 3 commands on disk ─────────────────
  1. bash(command="puzzle bee --letters VALIDTY --cente...")
     → 24
  [1] puzzle bee --letters VALIDTY --center V --json | jq '[.words[] | select((.word|length) >= 5)] | length'
```

The MCP agent has one move: call the tool, receive all 34 words with their scores, and count them in-context. That is 1,665 characters of intermediate result dragged through the context window, and the counting shows up as 428 output tokens because the model reasons over the list.

The briefed CLI agent pipes to `jq` and **two bytes** come back. `24\n`. The 34 words existed, were filtered, and were discarded inside the shell — they never touched the context window. 2.3x fewer input tokens and 4.5x fewer output tokens than MCP, for identical work.

**This is the strongest argument against MCP**, and it generalizes far past word puzzles: any time the useful answer is an aggregate, a filter, or a join over a large intermediate, MCP makes you pay for the intermediate and a shell does not.

### 3. The counterweight did not survive contact with the data

The predicted third asymmetry was: MCP is self-describing, so on a task nobody briefed, the MCP agent already knows the schema while the CLI agent burns turns on `--help`.

Neither system prompt mentions crossword patterns. The task: *find every dictionary word matching `C_O__W_RD`*.

| arm | input tok | output tok | round-trips | correct |
|---|---:|---:|---:|---:|
| MCP | 2548 ± 0 | 110 ± 1 | 2.0 | 5/5 |
| CLI | **1637 ± 593** | 124 ± 33 | **2.2** | 5/5 |

The CLI agent won this one too, and mostly never spent a turn on `--help`. What it typically wrote:

```bash
puzzle crossword --pattern "C_O__W_RD" --json 2>/dev/null || puzzle crossword --help
```

It guessed the subcommand and flag from ordinary Unix convention, and hedged the guess with a fallback in the *same* round-trip. The discovery cost the theory predicted was real but it was usually paid in about twenty output tokens of shell, not in an extra turn. The large spread (±593) is one run in five that guessed `puzzle pattern` instead of `puzzle crossword` and needed a recovery turn — so the cost exists, it is just intermittent and small.

**Report this honestly in the room.** The self-description advantage is real in principle and it did not show up here, because a conventionally-named CLI with a `--help` is itself a discovery mechanism, and the model is fluent in that convention. Where MCP's schema genuinely wins is where convention gives no help: unguessable enums, non-obvious required-field combinations, tools whose names do not telegraph their arguments. `puzzle crossword --pattern` was too guessable to be a fair test of it, and pretending otherwise would be rigging the demo.

The place discovery *did* cost real tokens was task 2: the unbriefed CLI agent guessed `.[] | select(...)` for the JSON shape, got an error, ran `jq '.'` to dump the whole payload into context, and only then wrote the right filter — 4240 input tokens against 1449 once it knew the shape. **Discovery cost is real; it just lands on the output schema, not the invocation.** MCP's structured output schema hands the model that for free.

### 4. The baseline

| arm | input tok | output tok | wall | correct |
|---|---:|---:|---:|---:|
| MCP | 3339 ± 0 | 165 ± 9 | 7.5s | 5/5 |
| CLI | 2217 ± 0 | 124 ± 1 | 4.9s | 5/5 |

Identical work, both sides briefed: CLI uses **34% fewer input tokens** with only 3 capabilities a side. Treat the wall-clock numbers with suspicion — they are dominated by API latency, and individual MCP runs varied from 3.7s to 14.5s across the session. Tokens are the reliable measurement here; time is not.

## The honest conclusion

**On tokens, the CLI wins, and it wins on every task measured.** With 3 capabilities it is 34% cheaper on input; with 40 it is 86% cheaper; on a composable aggregate it is 2.3x cheaper on input and 4.5x cheaper on output. We went in expecting to split the result, and expecting a rising CLI discovery cost at 40 commands to be the counterweight. Neither happened.

That does not make MCP a mistake. It makes the trade explicit:

**MCP buys you:**
- **Discovery of output shape.** The model knows what comes back before it calls. Task 2 shows exactly what not knowing costs.
- **Type safety at the boundary.** Arguments are validated against a schema before any code runs; `ToolError` is a defined failure channel. A shell agent's failure mode is an arbitrary string and exit status 2.
- **Enforceable permissions.** This is the one with no CLI equivalent at all. FastMCP's `Depends()` injects a parameter that is **excluded from the schema entirely** — the model cannot see it, set it, or spoof it (see `02`'s README). There is no way to hand an agent `bash` and withhold "the ability to run something you did not anticipate". Every capability on the PATH, and every capability the model can install, is in scope. If that matters — regulated data, production credentials, multi-tenant isolation — the token savings are not the deciding variable.
- **A single audit seam.** `02`'s logging middleware sees every call because every call crosses one place. `bash` gives you a command string.

**A CLI buys you:**
- **Composition.** Pipes, `jq`, `head`, `wc`. Intermediate results never enter the context window.
- **A flat tool budget, measured.** 2220 → 2220 → 2217 input tokens across 3, 15 and 40 capabilities. Capabilities live on disk, not in context.
- **Ubiquity.** No server, no adapter, no version pin. `puzzle` runs in CI, in a Makefile, and in your own hands with no model in the loop.

The shape the numbers actually support: **MCP pays fixed input tokens per turn and buys certainty; the CLI pays variable, occasional discovery tokens and buys a flat baseline.** The variable cost showed up as spread (±1090 in one cell) rather than as a trend, and it never scaled with catalogue size, because the agent guessed rather than enumerated.

The practical reading: **use MCP where the boundary needs to be enforced or the output schema needs to be discovered; use a CLI where the work needs to compose or the catalogue is large.** And keep the tool count small either way — 40 tools is not a richer server, it is a ~6,500-token entry fee on every turn.

### The synthesis worth naming

Both columns above are converging on the same answer, and it is neither of these designs: **let the model write code that calls the tools, and run that code somewhere else.**

Instead of the model invoking `solve_spelling_bee` and receiving 34 words, it writes a small program that calls the tool, filters, aggregates, and returns `24`. The tool definitions are loaded on demand — read from the filesystem as importable modules rather than injected into every request — so the schema tax scales with what you actually use instead of what you have installed. And the intermediate results live in the execution environment, not the context window. That is MCP's typed, permissioned boundary with the shell's composition, which is exactly the pair of properties the table above says you currently have to choose between. Anthropic has published this pattern as "code execution with MCP"; MCP's own Apps/`mcp-run-python` work points the same direction.

**We did not build it here** — this folder is a measurement, and adding a third arm would have made it an advocacy piece. But when someone in the room says "so which one do I pick", that is the direction the answer is moving.

## Caveats, stated plainly

- **One model, one task family, small payloads.** Word puzzles produce kilobyte-scale results. The composition advantage grows with payload size; a tool returning 200KB of JSON would widen the gap enormously. Nothing here says how it behaves at that scale.
- **Wall clock is API latency.** Reported for completeness, not for conclusions.
- **Input-token counts include the system prompt and conversation history**, summed across all round-trips. That is the real bill, but it means a run with more turns pays for its history twice.
- **No prompt caching.** Anthropic's prompt caching can amortize a large static tool block across turns within a session, which would soften — not eliminate — the tool-count tax. Measuring that is a good follow-up and is not measured here.
- **The pad capabilities are never called by either arm.** That is the point: MCP pays their full schema anyway, and the CLI does not.
- **The CLI agent never ran `ls`.** So this measures a *guessable* catalogue. Badly-named commands, or a task forcing enumeration, would likely put a real discovery cost on the CLI arm that 40 plausible names did not.
- **Round-trips and tool calls are counted separately.** `show_tools` gives the tool-call count; `usage_metadata` gives the round-trip count. A turn that calls no tool is still a request you pay input tokens for, so they are not interchangeable.

## Files

| File | What it is |
|---|---|
| `cli/puzzle` | The CLI — three solvers, `--json` output that composes with `jq`, no model required |
| `cli/pad/` | 37 generated pad commands with real `--help`, the CLI mirror of the MCP pad tools |
| `cli/make_pad.py` | Generates `cli/pad/` from `pad_catalog.py` |
| `pad_catalog.py` | The 37 pad capabilities, shared by both arms so they pad identically |
| `mcp_server.py` | The MCP arm — same solvers, plus a `--tools N` knob that pads to 40 |
| `agent_mcp.py` | Agent with MCP tools |
| `agent_cli.py` | Agent with one `bash` tool; `--capabilities N` sets the PATH size, `--brief` adds the output schema MCP gives away free |
| `tasks.py` | The three task prompts, byte-identical across both arms |
| `metrics.py` | Token/round-trip accounting from `usage_metadata` — measured, never estimated |
| `benchmark.py` | The harness: runs the matrix N times, writes `results/` |
| `verify_solvers.py` | Proves the solver bodies are byte-identical to `shared/solvers_reference.py` |
| `results/results.json` | Every run, every metric, every command the agents issued |
| `results/chart.txt` | Rendered ASCII chart |
| `results/tool_scaling.md` | The capabilities-in-context vs. capabilities-on-disk tables |
| `results/traces.txt` | A full tool-call trace per cell, with verbatim commands |
| `results/cli_catalog.txt` | `ls` of the CLI agent's PATH at 3, 15 and 40 capabilities |
