# Sample runs

Commands are from the repo root, with the virtualenv active. Sections 1–4 need
`ANTHROPIC_API_KEY`; sections 5–7 need no key and no network.

## 1. Spelling Bee

```bash
python 02-mcp-puzzlemaster/agent_bee.py --letters VALIDTY --center V
```

One `solve_spelling_bee` call, then **34 words, 171 points, pangram VALIDITY**.
(NYT's curated answer for this 2026-08-28 puzzle was 21 words / 119 points.)

## 2. Crossword

```bash
python 02-mcp-puzzlemaster/agent_crossword.py --pattern C_O__W_RD
```

Exactly one match, **CROSSWORD**.

## 3. Wordle

```bash
python 02-mcp-puzzlemaster/agent_wordle.py --guess CRANE --feedback gybbb
```

**34 candidates** remaining (CHOIR, CHORD, CURIO, …).

```bash
python 02-mcp-puzzlemaster/agent_wordle.py --guess CRANE --feedback gybbb --guess CHOIR --feedback gggby
```

Exactly one candidate left, **CHORD**.

## 4. One agent, all three games

`agent_puzzlemaster.py` holds every solver, so the tool is chosen by the model
rather than by which script you started. It takes free text, not typed flags.

With the game named:

```bash
python 02-mcp-puzzlemaster/agent_puzzlemaster.py \
  --ask "I'm playing Spelling Bee today. Letters are VALIDTY, V in the middle."
```

```
  1. solve_spelling_bee(agent_name="agent-puzzlemaster", letters="VALIDTY", center="V")
```

Same **34 words, 171 points, pangram VALIDITY** as section 1.

With no game named at all — the shape of the input decides:

```bash
python 02-mcp-puzzlemaster/agent_puzzlemaster.py --ask "what fits C_O__W_RD?"
```

```
  1. solve_crossword_pattern(agent_name="agent-puzzlemaster", pattern="C_O__W_RD")
```

One match, **CROSSWORD**.

```bash
python 02-mcp-puzzlemaster/agent_puzzlemaster.py \
  --ask "I played CRANE and got green, yellow, then three blacks"
```

```
  1. solve_wordle(agent_name="agent-puzzlemaster", guesses=["CRANE"], feedback=["gybbb"])
```

**34 candidates** — note that the agent translated "green, yellow, then three
blacks" into `gybbb` itself. Nobody passed it a feedback string.

Run bare to do all three in one conversation, which puts three different tools
in one audit-log session:

```bash
python 02-mcp-puzzlemaster/agent_puzzlemaster.py
```

## 5. A failing call

```bash
python 02-mcp-puzzlemaster/agent_bee.py --letters ABC --center A
```

`ToolError: need exactly 7 distinct letters, got 3`, and a row in `usage.db`
with `ok=0`:

```bash
sqlite3 02-mcp-puzzlemaster/usage.db "SELECT agent_name, tool, ok, outputs FROM invocations WHERE ok=0 LIMIT 1;"
```

## 6. Seed a history — no API key

```bash
python 02-mcp-puzzlemaster/seed_usage.py --reset
```

```
seeded 24 invocations (21 ok, 3 failed)

Tool usage by agent — 24 invocation(s), 3 agent(s)

agent-wordle     ########################################   12  avg    13ms  (1 failed)
agent-bee        #######################                     7  avg    10ms  (1 failed)
agent-crossword  #################                           5  avg     4ms  (1 failed)
```

```bash
python 02-mcp-puzzlemaster/monitor.py --graph agent
python 02-mcp-puzzlemaster/monitor.py --graph tool
```

```
Tool usage by agent — 25 invocation(s), 4 agent(s)

agent-wordle     ########################################   12  avg    13ms  (1 failed)
agent-bee        #######################                     7  avg    10ms  (1 failed)
agent-crossword  #################                           5  avg     4ms  (1 failed)
seed             ###                                         1  avg     0ms
```

```
Tool usage by tool — 26 invocation(s), 4 tool(s)

solve_wordle             ########################################   12  avg    13ms  (1 failed)
solve_spelling_bee       #######################                     7  avg    10ms  (1 failed)
solve_crossword_pattern  #################                           5  avg     4ms  (1 failed)
usage_graph              #######                                     2  avg     0ms
```

The totals climb between the two renders because `usage_graph` is itself a
logged tool call. `--reset` clears the table first; without it, rows accumulate.

## 7. Export the audit trail — no API key

```bash
python 02-mcp-puzzlemaster/monitor.py --export exports/results.csv
head -c 400 02-mcp-puzzlemaster/exports/results.csv
```

```
id,ts,agent_name,tool,inputs,outputs,duration_ms,ok
```

One row per invocation — 27 after section 6.

```bash
python -c "import csv; r=list(csv.DictReader(open('02-mcp-puzzlemaster/exports/results.csv'))); \
print(len(r), 'rows;', sum(x['ok']=='0' for x in r), 'failures;', \
sorted({x['agent_name'] for x in r}))"
```

```
27 rows; 3 failures; ['agent-bee', 'agent-crossword', 'agent-wordle', 'monitor', 'seed']
```

Both `inputs` and `outputs` are valid JSON. Very large outputs are stored as a
`{"truncated_chars": …, "preview": …}` object.
