# 02 — PuzzleMaster

Three agents — bee, crossword and wordle — sharing one MCP server, which logs
every call to a SQLite audit trail.

## Run

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

## Prompts

| agent | type this | you get |
|---|---|---|
| `agent_bee.py` | `today's bee is VALIDTY, V in the middle` | 34 words, 171 points, pangram VALIDITY |
| `agent_crossword.py` | `what fits C_O__W_RD?` | one match, CROSSWORD |
| `agent_wordle.py` | `I played CRANE and got green, yellow, then three blacks` | 34 candidates remaining |

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**Connection error from an agent** — the server is not running. Start it in
another terminal first.

**Empty graph from `monitor.py`** — nothing has been logged yet. Run
`python 02-mcp-puzzlemaster/seed_usage.py --reset`.
