# 02 — PuzzleMaster

Four agents — bee, crossword, wordle, and one that handles all three — sharing
one MCP server, which logs every call to a SQLite audit trail.

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
python 02-mcp-puzzlemaster/agent_puzzlemaster.py
```

Each opens a chat. Every call also appears in the server terminal.

## Prompts

| agent | prompt |
|---|---|
| `agent_bee.py` | `today's bee is VALIDTY, V in the middle` |
| `agent_crossword.py` | `what fits C_O__W_RD?` |
| `agent_wordle.py` | `I played CRANE and got green, yellow, then three blacks` |
| `agent_puzzlemaster.py` | any of the above, in any order, in one session |

The bee returns 34 words, 171 points, pangram VALIDITY. The crossword returns
one match, CROSSWORD. Wordle returns 34 candidates remaining.

## The fourth agent — who picks the tool?

The first three agents each take one slice of the server and throw the rest
away:

```python
tools = [t for t in await load_mcp_tools(session) if t.name == MY_TOOL]
```

Which game you are playing is therefore decided by *which process you start*.
`agent_puzzlemaster.py` changes one character — `==` becomes `in` — and keeps
all three solvers:

```python
MY_TOOLS = ("solve_spelling_bee", "solve_crossword_pattern", "solve_wordle")
tools = [t for t in await load_mcp_tools(session) if t.name in MY_TOOLS]
```

Now tool selection is the model's job. It routes two ways, and both are worth
demonstrating:

**With a descriptor** — the user names the game:

```
you › I'm playing the Spelling Bee. Letters VALIDTY, V in the middle.
you › switch to Wordle — I opened with CRANE, gybbb
```

**Without one** — the user goes straight to the ask and the shape of the input
decides:

```
you › what fits C_O__W_RD?          → solve_crossword_pattern
you › VALIDTY, V in the centre       → solve_spelling_bee
you › CRANE gave me green, yellow, then three blacks   → solve_wordle
```

Seven letters plus a centre, a pattern of letters and underscores, and guesses
paired with colour feedback are each unambiguous on their own, so the system
prompt tells the model to route on shape and to ask a clarifying question only
when the input genuinely fits nothing.

**Why this matters.** With one tool the model *cannot* pick wrong, so a correct
call proves nothing about it. With three, the `tools invoked` line is the first
place in this curriculum where the routing is actually on trial — and the audit
table records every route it took, right or wrong, under `agent-puzzlemaster`:

```bash
python 02-mcp-puzzlemaster/monitor.py --graph tool
```

The audit tools (`usage_graph`, `export_results`) are deliberately *not* handed
to this agent. `monitor.py` owns those; giving a puzzle agent a "chart my own
usage" tool invites it to wander. Narrowing the tool surface is a design
decision, not an oversight — that is the same decision the other three agents
make, taken to a different point.

## One-shot mode

Every agent here answers once and exits when given arguments, which is what
`samples/` and the tests use. `agent_puzzlemaster.py` takes free text rather
than typed flags, because there is no single flag set that fits three games:

```bash
python 02-mcp-puzzlemaster/agent_puzzlemaster.py --ask "what fits C_O__W_RD?"
```

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**Connection error from an agent** — the server is not running. Start it in
another terminal first.

**`UnicodeEncodeError: 'charmap' codec`** — Windows console only. The tool-call
trace uses box-drawing characters. Set `PYTHONIOENCODING=utf-8` before running.

**Empty graph from `monitor.py`** — nothing has been logged yet. Run
`python 02-mcp-puzzlemaster/seed_usage.py --reset`.
