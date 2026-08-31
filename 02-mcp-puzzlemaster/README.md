# 02 — PuzzleMaster: many agents, one server

**The one idea:** once several agents share a single MCP server, you get observability and reuse you cannot get from tools scattered across three codebases — one dictionary loaded once, one place that sees every call, and one table you can graph and export.

Three agents (Spelling Bee, Crossword, Wordle), one server, one 172,823-word dictionary, one audit trail.

## Setup

From the repo root, with the shared virtualenv active:

```bash
pip install -r ../requirements.txt
cp .env.local.example .env.local    # put your key in it
cd 02-mcp-puzzlemaster
```

`mcp==1.29.1` is pinned deliberately — `langchain-mcp-adapters` requires `mcp<2.0.0`, and an unpinned `pip install mcp` breaks the demo.

## Run

One server, three agents, three separate processes.

**Terminal 1 — the shared server.** Start it once and leave it up.

```bash
./.venv/bin/python 02-mcp-puzzlemaster/mcp_server.py
# [puzzlemaster] loaded 172,823 words from enable1.txt in 10.3ms — once, for every agent
# [puzzlemaster] listening on http://127.0.0.1:8002/mcp
```

That first line is the argument this folder makes. The dictionary is loaded
**once**, and it stays loaded no matter how many agents connect.

**Terminal 2 — talk to any of them.** No arguments: you get a conversation.

```bash
./.venv/bin/python 02-mcp-puzzlemaster/agent_bee.py
./.venv/bin/python 02-mcp-puzzlemaster/agent_crossword.py
./.venv/bin/python 02-mcp-puzzlemaster/agent_wordle.py
```

```
you › today's bee is VALIDTY, V in the middle
you › what fits C_O__W_RD?
you › I played CRANE and got green, yellow, then three blacks
```

Every call lands in terminal 1 as it happens, and every one is written to the
audit log with the calling agent's name.

**Then look at what the server saw:**

```bash
./.venv/bin/python 02-mcp-puzzlemaster/monitor.py --graph agent
./.venv/bin/python 02-mcp-puzzlemaster/monitor.py --graph tool
./.venv/bin/python 02-mcp-puzzlemaster/monitor.py --export /tmp/usage.csv
```

No API key needed for those — they read the log the server already wrote.

**No key, no network?** `seed_usage.py` generates a realistic history so the
monitoring demo works regardless.

## What to notice

**One dictionary, loaded once.** On startup the server prints to *stderr*:

```
[puzzlemaster] loaded 172,823 words from enable1.txt in ~10ms — once, for every agent
```

Once. Not once per call, and not three times across three agent processes. In 00 each agent owns its own copy of the word list; that is three copies to keep in sync, and a fourth as soon as someone writes a fourth agent. Here the load cost is paid at startup and every agent, present and future, reads the same list — so "the Bee agent and the Wordle agent disagreed about whether ZORIL is a word" stops being possible.

**The usage graph spans all three agents.** No agent can produce this. It only exists because every call crosses one seam:

```
Tool usage by agent — 24 invocation(s), 3 agent(s)

agent-wordle     ########################################   12  avg    13ms  (1 failed)
agent-bee        #######################                     7  avg    10ms  (1 failed)
agent-crossword  #################                           5  avg     4ms  (1 failed)
```

Group by `tool` instead and you are looking at the same rows sliced the other way — which capability is actually earning its keep. Failures are in there too, logged with `ok=0`. An audit trail that only records successes is not an audit trail; the row you most want is the one where an agent was quietly failing in a loop.

**The CSV export.** `export_results` writes every logged column — `id, ts, agent_name, tool, inputs, outputs, duration_ms, ok` — and it is two things at once:

1. An **audit trail**: who called what, when, with what, and did it work.
2. A **ready-made eval dataset**: every row is an input/output pair nobody had to write by hand. Filter to `ok=1`, and you have regression cases straight from real usage. Filter to `ok=0`, and you have your bug list.

That dataset exists only because the calls funnel through one place. Scattered local tools give you neither.

## `agent_name` is telemetry, not authentication

Every tool here takes an explicit `agent_name: str`, and the calling agent passes its own name. Be honest with the room about what that is worth.

`agent_name` is an ordinary tool parameter. It is in the JSON schema the model reads, and the model fills it in. So it can be wrong — a distracted model passes `"assistant"` — and it can be *made* wrong: nothing stops an agent from claiming to be `agent-bee`. It is honest attribution for telemetry, not an identity claim you can enforce.

The production answer over HTTP is `tool_interceptors` injecting an `X-Agent-Id` header: identity travels in the transport, out of the model's reach. **But stdio has no header channel at all** — `langchain-mcp-adapters` only merges headers for `sse`/`http`/`streamable_http`. Over stdio there is nowhere else to put it, which is exactly why the explicit parameter is the right baseline here, and why the honesty matters.

Contrast with FastMCP's `Depends()`:

```python
from fastmcp.dependencies import Depends

@mcp.tool
def solve(pattern: str, caller: str = Depends(get_caller_id)) -> dict: ...
```

`Depends()` parameters are **excluded from the generated schema entirely**. The model cannot see `caller`, cannot set it, and cannot spoof it, because as far as the model is concerned it does not exist.

The distinction worth naming: `agent_name` is **trustworthy-because-convenient** — nothing gains from lying, so in practice it is accurate. `Depends()` is **trustworthy-because-unreachable** — lying is not an available move. Only the second survives contact with an adversary, or with a model having a bad day. Use the first for telemetry; never use it for authorization.

## Design notes

**Middleware, not a decorator, for the logging.** FastMCP's `on_call_tool` middleware hook is the one seam every tool call already crosses, and it sees everything the audit table needs: the tool name (`context.message.name`), the raw arguments (`context.message.arguments`, including `agent_name`), the result or the exception, and the timing. A per-tool decorator would give the same data but would have to be remembered on every new tool; the middleware audits tool #6 for free the day it is written. That is the folder's argument in miniature — centralizing created a place to stand.

**The audit tools are audited too.** `usage_graph` and `export_results` also take `agent_name`, so running `monitor.py` adds a row under the name `monitor`. It shows up on the next graph. That is honest behaviour, not a bug: the log records everything crossing the seam.

**Never print to stdout in the server.** stdout *is* the stdio protocol channel. One stray `print()` corrupts the JSON-RPC stream and the client dies with a parse error. Diagnostics go to stderr; records go to SQLite.

**One session per agent run.** The agents hold the stdio connection open with `async with client.session("puzzlemaster")` instead of calling `client.get_tools()` and letting each tool call reconnect. Reconnecting respawns the server subprocess — and reloads the 172k-word dictionary — on every single call. Watch the stderr banner: it should appear once per agent run, not once per tool call. That is what makes "loaded once" true in practice and not just in principle.

**SQLite, not memory.** `usage.db` survives restarts. "Monitor usage over time" is meaningless if the counter resets when the process does.

**Solver bodies are byte-identical to `shared/solvers_reference.py`.** They are pasted in verbatim, with thin `@mcp.tool` wrappers around them that add `agent_name`, hand in the shared `WORDS` list, and translate `ValueError` into `ToolError`. Diff them against the reference — that they do not change from 00 to 01 to 02 *is* the lesson. What changes is only the seam.

**`ToolError` for user-facing failures.** `ToolError` messages always reach the client; every other exception is an internal detail you do not want leaking into an LLM transcript.

## Files

| File | What it is |
|---|---|
| `mcp_server.py` | The shared server: 3 solver tools + `usage_graph` + `export_results`, logging middleware, one word-list load |
| `agent_bee.py` | Spelling Bee agent — gets only `solve_spelling_bee` |
| `agent_crossword.py` | Crossword agent — gets only `solve_crossword_pattern` |
| `agent_wordle.py` | Wordle agent — gets only `solve_wordle` |
| `monitor.py` | Reads the audit trail via the MCP tools; no API key needed |
| `seed_usage.py` | Generates a multi-agent history with no API key — the demo's safety net |
| `usage.db` | The audit trail (gitignored; created on first run) |
