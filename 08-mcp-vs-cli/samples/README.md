# Sample runs

Copy-pasteable. Run from `08-mcp-vs-cli/` with the shared virtualenv active.

Anything needing a key reads it from `.env.local` at the repo root — copy
`.env.local.example` and fill it in once; you never export anything in a shell.
Every agent prints the tools it invoked before printing its answer.

## 1. The CLI alone — no model, no API key

```bash
cli/puzzle bee --letters VALIDTY --center V
```

Expected: `34 words, 171 points, pangrams: VALIDITY`, then the scored word list.
(ENABLE1 over-generates against NYT's curated 21 words / 119 points — see `02`'s README.)

```bash
cli/puzzle bee --letters VALIDTY --center V --json | jq '[.words[] | select(.word|length >= 5)] | length'
```

Expected: `24`. All 34 words were produced, filtered and discarded inside the
shell; two bytes came out.

Edge case — the CLI refuses bad input rather than guessing:

```bash
cli/puzzle bee --letters ABC --center A; echo "exit=$?"
```

Expected: `puzzle: error: need exactly 7 distinct letters, got 3` on stderr, `exit=2`.

## 2. Prove the experiment is controlled — no API key

```bash
python verify_solvers.py
```

Expected: eight `identical` lines and
`OK — 4 solvers byte-identical across 2 implementations.` Non-zero exit if anything drifted.

## 3. Capabilities in context vs. capabilities on disk — needs a key

The MCP arm, with 3 tools and then 40:

```bash
python agent_mcp.py --task solve --tools 3
python agent_mcp.py --task solve --tools 40
```

Expected metrics line on stderr:

```
[mcp/solve/3 tools]  in=3339  out=167 llm_calls=2 tool_calls=1 ... correct=True
[mcp/solve/40 tools] in=16309 out=166 llm_calls=2 tool_calls=1 ... correct=True
```

Same answer, same single tool call — **4.9x the input tokens**. The tool-call
trace above it shows exactly one tool invoked while 40 definitions sat in
context being billed on every turn.

Now the CLI arm at the same two levels:

```bash
python agent_cli.py --task solve --capabilities 3
python agent_cli.py --task solve --capabilities 40
```

Expected: `in=2217` **both times**. Thirty-seven extra commands appeared on the
PATH and the input cost did not move. See what the agent's PATH held:

```bash
cat results/cli_catalog.txt
```

## 4. Composition, with and without the output schema — needs a key

```bash
python agent_cli.py --task aggregate            # has to discover the JSON shape
python agent_cli.py --task aggregate --brief    # told the shape up front
```

Expected: roughly `in=3908 out=161 llm_calls=3` unbriefed versus
`in=1449 out=96 llm_calls=2` briefed. The unbriefed run typically guesses a jq
filter, fails, dumps the whole payload to learn the shape, then retries. That
gap is what MCP's output schema gives you for free.

The briefed trace: one call, two bytes back.

```
  1. bash(command="puzzle bee --letters VALIDTY --cente...")
     → 24
```

Compare against MCP on the same task:

```bash
python agent_mcp.py --task aggregate
```

Expected: `in=3345 out=428 llm_calls=2`, and a trace whose result preview is the
full 34-word list. The output tokens are higher because the model counts the
list in context, having had no way to filter before the words arrived.

## 5. The full benchmark — needs a key, ~12 minutes, ~95 API calls

```bash
python benchmark.py --runs 5
```

Writes `results.json`, `chart.txt`, `tool_scaling.md`, `traces.txt` and
`cli_catalog.txt`, and prints the chart. Committed results are already in
`results/`.

Re-render the committed numbers without spending anything:

```bash
python benchmark.py --render-only
```

Verify the key really is coming from `.env.local`:

```bash
env -u ANTHROPIC_API_KEY python agent_cli.py --task solve
```

Expected: it works. Remove the key from `.env.local` too and you get a message
naming the file, not a stack trace.
