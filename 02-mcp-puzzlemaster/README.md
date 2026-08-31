# 02 — PuzzleMaster

Three agents — bee, crossword and wordle — sharing one MCP server, which logs
every call to a SQLite audit trail.

## Files

| | |
|---|---|
| `mcp_server.py` | The shared server: three solver tools, plus `usage_graph` and `export_results` |
| `agent_bee.py` | Spelling Bee agent |
| `agent_crossword.py` | Crossword agent |
| `agent_wordle.py` | Wordle agent |
| `monitor.py` | Reads the audit trail; no API key needed |
| `seed_usage.py` | Generates a usage history with no API key |
| `usage.db` | The audit trail (created on first run, gitignored) |
| `samples/` | Captured runs |

## Run it

All commands are from the repo root, with the virtualenv active.

Start the server and leave it running:

```bash
python 02-mcp-puzzlemaster/mcp_server.py
```

```
[puzzlemaster] loaded 172,823 words from enable1.txt in 10.3ms — once, for every agent
[puzzlemaster] listening on http://127.0.0.1:8002/mcp
```

In a second terminal, run any of the agents:

```bash
python 02-mcp-puzzlemaster/agent_bee.py
python 02-mcp-puzzlemaster/agent_crossword.py
python 02-mcp-puzzlemaster/agent_wordle.py
```

Each opens a chat. Every call also appears in the server terminal.

## Sample prompts

| agent | type this | you get |
|---|---|---|
| `agent_bee.py` | `today's bee is VALIDTY, V in the middle` | 34 words, 171 points, pangram VALIDITY |
| `agent_crossword.py` | `what fits C_O__W_RD?` | one match, CROSSWORD |
| `agent_wordle.py` | `I played CRANE and got green, yellow, then three blacks` | 34 candidates remaining |

## See what the server logged

No API key needed — these read the log the server already wrote.

```bash
python 02-mcp-puzzlemaster/monitor.py --graph agent
python 02-mcp-puzzlemaster/monitor.py --graph tool
python 02-mcp-puzzlemaster/monitor.py --export /tmp/usage.csv
```

```
Tool usage by agent — 24 invocation(s), 3 agent(s)

agent-wordle     ########################################   12  avg    13ms  (1 failed)
agent-bee        #######################                     7  avg    10ms  (1 failed)
agent-crossword  #################                           5  avg     4ms  (1 failed)
```

With no API key and no network, generate a history first:

```bash
python 02-mcp-puzzlemaster/seed_usage.py --reset
```

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**Connection error from an agent** — the server is not running. Start it in
another terminal first.

**Empty graph from `monitor.py`** — nothing has been logged yet. Run
`python 02-mcp-puzzlemaster/seed_usage.py --reset`.
