# Sample runs

Every command below is copy-pasteable from `02-mcp-puzzlemaster/`. Expected output is stated so you know immediately whether your environment is broken.

Sections 1–3 need `ANTHROPIC_API_KEY`. Sections 4–6 need **no key and no network** — that is deliberate, so the monitoring demo still works if the key or the network dies mid-session.

---

## 1. Spelling Bee — normal run

```bash
python agent_bee.py --letters VALIDTY --center V
```

Expected: the agent calls `solve_spelling_bee` once and reports **34 words, 171 points, pangram VALIDITY**. Prose varies; those three numbers must not.

> Worth saying out loud: NYT's curated answer for this real 2026-08-28 puzzle was **21 words / 119 points**. ENABLE1 over-generates against editorial curation. That gap is the lesson — a deterministic tool and a curated ground truth are not the same thing.

## 2. Crossword — normal run

```bash
python agent_crossword.py --pattern C_O__W_RD
```

Expected: exactly one match, **CROSSWORD**.

## 3. Wordle — normal run and multi-turn

```bash
python agent_wordle.py --guess CRANE --feedback gybbb
```

Expected: **34 candidates** remaining (CHOIR, CHORD, CURIO, …).

Two turns — repeat the flags in matching order:

```bash
python agent_wordle.py --guess CRANE --feedback gybbb --guess CHOIR --feedback gggby
```

Expected: exactly one candidate left, **CHORD**. The count must strictly shrink turn over turn; if it grows, duplicate-letter handling is broken.

## 4. Edge case — failures are logged, not swallowed

```bash
python agent_bee.py --letters ABC --center A
```

Expected: the tool raises `ToolError: need exactly 7 distinct letters, got 3`, the agent reports the problem in plain language rather than inventing words, and a row lands in `usage.db` with `ok=0`. Check it:

```bash
sqlite3 usage.db "SELECT agent_name, tool, ok, outputs FROM invocations WHERE ok=0 LIMIT 1;"
```

Without an API key, `seed_usage.py` produces the same three failure rows.

## 5. Multi-agent sequence — the monitoring demo (no API key)

```bash
python seed_usage.py --reset
```

Runs 24 invocations across all three agents — deliberately lopsided, with three intentional failures — through the same server, same middleware, same table. Expected tail:

```
seeded 24 invocations (21 ok, 3 failed)

Tool usage by agent — 24 invocation(s), 3 agent(s)

agent-wordle     ########################################   12  avg    13ms  (1 failed)
agent-bee        #######################                     7  avg    10ms  (1 failed)
agent-crossword  #################                           5  avg     4ms  (1 failed)
```

Now the two views, by agent and by tool:

```bash
python monitor.py --graph agent
python monitor.py --graph tool
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

The totals climb between the two renders, and `seed` / `monitor` appear as agents. That is correct: `usage_graph` is itself a logged tool call. The audit trail records everything crossing the seam, including the tools that read it.

Drop the `--reset` and run the seeder again to watch every bar grow — the table is SQLite on disk, so it survives restarts.

## 6. Export the audit trail / eval dataset (no API key)

```bash
python monitor.py --export exports/results.csv
head -c 400 exports/results.csv
```

Expected: prints the absolute path it wrote, and the CSV opens with

```
id,ts,agent_name,tool,inputs,outputs,duration_ms,ok
```

then one row per invocation — 27 after section 5. Verify it rather than trusting the return value:

```bash
python -c "import csv; r=list(csv.DictReader(open('exports/results.csv'))); \
print(len(r), 'rows;', sum(x['ok']=='0' for x in r), 'failures;', \
sorted({x['agent_name'] for x in r}))"
```

Expected: `27 rows; 3 failures; ['agent-bee', 'agent-crossword', 'agent-wordle', 'monitor', 'seed']`

Both `inputs` and `outputs` are valid JSON (very large outputs are stored as a `{"truncated_chars": …, "preview": …}` object, still valid JSON). Every `ok=1` row is a regression test nobody wrote; every `ok=0` row is a bug report nobody filed.
