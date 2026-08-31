# 01 — the same solver, moved behind MCP

**The one idea:** moving a working agent tool behind an MCP server changes the
seam around your code, not your code — the solver body here is byte-identical
on both sides, and the model can't tell the difference.

Three files, and you should read them in this order:

| File | What it is |
|---|---|
| `agent_with_tool.py` | BEFORE — LangChain agent, solver as a local `@tool` |
| `mcp_server.py` | The same solver, exposed as `@mcp.tool` over stdio |
| `agent_with_mcp.py` | AFTER — same agent, no local tool, tools come from MCP |

## Setup

One virtualenv for the whole repo. From the repo root:

```bash
cd ~/mcp-training                   # the repo root, wherever you cloned it
./setup.sh                          # venv + pinned deps + solver tests
cp .env.local.example .env.local    # then put your ANTHROPIC_API_KEY in it
```

Run any agent with the repo's own interpreter — no `activate` needed, and it
cannot pick up the wrong virtualenv:

```bash
../.venv/bin/python agent_with_mcp.py
```

`mcp==1.29.1` is pinned deliberately. PyPI's latest is 2.x, but
`langchain-mcp-adapters` requires `mcp<2.0.0`; an unpinned `pip install -U mcp`
breaks the demo.

## Run

The server is a **separate process**. That is the whole point of this folder, so
start it yourself rather than letting the agent spawn it.

**Terminal 1 — the server.** Leave it running; every tool call shows up here.

```bash
./.venv/bin/python 01-mcp-bee/mcp_server.py
# [bee] listening on http://127.0.0.1:8001/mcp
```

**Terminal 2 — the agents.** No arguments: you get a conversation.

```bash
./.venv/bin/python 01-mcp-bee/agent_with_tool.py    # local @tool
./.venv/bin/python 01-mcp-bee/agent_with_mcp.py     # same tool, over HTTP
```

Type the same thing into each:

```
you › today's bee is VALIDTY, V in the middle
you › now LAMPYRD with Y in the centre
you › which one had more words?
```

Both answer 34 words / 171 points / VALIDITY. Watch terminal 1 while you do it —
only the MCP run puts anything there.

That third question is worth pausing on: the trace prints
`(none — the model answered without calling a tool)`. It already had both
answers and knew not to call anything.

Then the punchline:

```bash
diff 01-mcp-bee/agent_with_tool.py 01-mcp-bee/agent_with_mcp.py
```

The solver is byte-identical. Only the seam moved.

## What to notice

Run the diff. It is the whole lesson:

```bash
diff agent_with_tool.py agent_with_mcp.py
```

Three things show up, and nothing else:

1. **The solver is gone** from `agent_with_mcp.py` — the `load_words` /
   `solve_spelling_bee` / `spelling_bee` block is deleted, not rewritten.
2. **A client is added** — `MultiServerMCPClient({...})` plus
   `tools = await client.get_tools()` replacing `tools = [spelling_bee]`.
3. **The tool call itself is unchanged.** Same tool name, same three arguments,
   same docstring driving the model's decision, same returned dict. From the
   model's point of view nothing happened at all.

Then diff the other pair, which is the claim this folder actually rests on:

```bash
diff <(sed -n '/^def load_words/,/^    }$/p' agent_with_tool.py) \
     <(sed -n '/^def load_words/,/^    }$/p' mcp_server.py)   # prints nothing
```

The solver is byte-identical, and identical to `shared/solvers_reference.py`.
Only the decorator differs: `@tool` → `@mcp.tool`.

A few more things worth pointing at on screen:

- **No schema anywhere.** Both sides derive the JSON Schema from the type hints
  and the docstring. The docstring is not documentation — it is the prompt the
  model reads to decide whether and how to call this thing.
- **stdout is the protocol.** `mcp_server.py` logs to stderr on purpose. Add one
  `print()` to a stdio server and you corrupt the JSON-RPC stream. This is the
  single most common way a first MCP server dies.
- **`agent_name` is honest, not secure.** The model fills it in, so it is
  attribution for telemetry, not authentication — a model can get it wrong or
  lie. Over HTTP the production answer is a `tool_interceptors` header, but
  stdio has no header channel at all, so an explicit parameter is the correct
  baseline here. Contrast FastMCP's `Depends()`, where injected parameters are
  excluded from the schema entirely and the model can never see them.
- **One line makes it company-wide.** The commented line at the bottom of
  `mcp_server.py` is `mcp.run(transport="http", host="0.0.0.0", port=8000)`.
  Same tool code, now reachable by every agent in the building instead of by
  one subprocess on one laptop.

### Inspect the server without an agent

```bash
fastmcp dev inspector mcp_server.py
```

That opens the browser-based MCP Inspector: list the tool, fill in `letters`,
`center` and `agent_name` by hand, call it, and watch the raw protocol traffic.
Do this before demoing anything with a model in the loop — it removes the model
as a variable.

Note it is `fastmcp dev inspector`, **not** `fastmcp dev`. The bare form was the
FastMCP 2.x spelling and it changed in 3.x; nearly every blog post is stale here.

## "Isn't this just an API with extra steps?"

Largely, yes — and for what you are looking at on this screen, entirely yes.

`agent_with_mcp.py` does strictly more work than `agent_with_tool.py` to reach
the same answer: it spawns a subprocess, does a protocol handshake, and
serializes a dict across a pipe, to call a function that was already sitting in
the same file. It is slower, it has more failure modes, and it is more code. For
one agent that you own end to end, MCP is pure overhead. Do not let anyone tell
you otherwise.

It starts paying at the **second consumer**. When Claude Desktop, a colleague's
agent, a Slack bot and a scheduled job all need this solver, the local-tool
version means four copies of the function, four schemas drifting apart, and four
places to patch. The MCP version means one implementation, one place to log,
one place to authorize, one place to fix — and any new client discovers the tool
by asking, with no client-side changes at all.

That is the trade. It is a real one, and it is worth making honestly: this folder
is the overhead. Folder 02 is the payoff.

## Samples

`samples/` has copy-pasteable commands with the exact output to expect,
including an error case.
