# 03 — Bookstore

Move a working LangChain agent onto an MCP server, then add write tools only an
admin agent can use.

## Run

What ships is the *before* picture: `starter/rightbookai_agent.py`, a working
LangChain agent whose tools run inside its own process. Run it first, so you
know what you are refactoring.

From the repo root, virtualenv active:

```bash
python 03-mcp-bookstore/starter/rightbookai_agent.py "Do you have The Midnight Library?"
```

Then, once you have built your version:

```bash
cd 03-mcp-bookstore/starter
python bookstore_server.py     # terminal 1
python agent_reader.py         # terminal 2
python agent_admin.py          # terminal 3
```

## Prompts

```
do you have The Midnight Library?
I have $65, build me a bundle of sci-fi and mystery
recommend 3 post-apocalyptic books under $20
add 'The Fifth Season' by N.K. Jemisin, Fantasy, $18.99
```

## What ships, and what you write

Present in `starter/`:

| | |
|---|---|
| `rightbookai_agent.py` | the working base agent. Tools imported, in-process. Leave it alone — it is the control you are refactoring away from. |
| `tools/*.py` | the tools as they exist today, natural-language parameters and all. What you are getting rid of. |
| `inventory.py` | search, scoring and the knapsack solver, already written. What you are keeping. |
| `test_exercise.py` | the specification. |
| `storedata.json` | the catalog. |

You write three files, into `starter/`, alongside those. None of them exists
yet; nothing in the repo creates them for you.

**`bookstore_server.py`** — the MCP server.

- Defines a module-level `mcp = FastMCP("bookstore")`. `test_exercise.py` does
  `import bookstore_server` and drives `bookstore_server.mcp` through FastMCP's
  in-memory client, so that filename and that variable name are part of the
  contract. Until the file exists the tests cannot import it and report so.
- Exposes exactly seven tools, named and shaped as `test_exercise.py`'s `SPEC`
  states: `search_books`, `get_book`, `recommend_books`, `build_bundle`
  (checkpoints A and B), then `add_book`, `update_book`, `delete_book`
  (checkpoint C). Every one takes `agent_name: str` as a required parameter.
- Every parameter is typed and, apart from `agent_name`, individually optional.
  The docstring is the only thing the model reads before deciding to call a
  tool, so state what comes back and enumerate the valid genres —
  `inventory.GENRES` holds them, and the model should never have to guess how
  this store spells "Science Fiction".
- Serves HTTP on `http://127.0.0.1:8003/mcp` by default. Take `--host`,
  `--port`, and a `--stdio` flag that serves over stdio instead — the transport
  a client would spawn rather than connect to. The server is its own process;
  you start it, and no agent starts it for you.
- **Never prints to stdout.** Under stdio transport stdout *is* the JSON-RPC
  channel, and one stray `print()` kills the client. Every diagnostic goes to
  `sys.stderr`. Log each invocation there — agent name, tool, arguments,
  outcome, duration — as `samples/README.md` shows.
- Computation is delegated to `inventory.py`. The server is a seam, not a
  reimplementation.

Copy the shape from `01-mcp-bee/mcp_server.py`: the `FastMCP` instance at
module scope, `logging.basicConfig(stream=sys.stderr)`, solver logic untouched
underneath, `mcp.run(...)` under `if __name__ == "__main__"`.

**`agent_reader.py`** — the client half of checkpoint A, and the shape every
agent in this repo follows. `01-mcp-bee/agent_with_mcp.py` is the file to copy
from. `rightbookai_agent.py` is the *old* shape — synchronous, tools imported,
key read directly — and deliberately not the model to follow here.

- Connects to the server you started in the other terminal. It does not start
  one. Two processes, over HTTP, via
  `MultiServerMCPClient({"bookstore": {"transport": "streamable_http", "url": ...}})`.
  Fail with a readable message when the server is not up.
- Loads **only the read tools**. Not "instructed not to write" — the write
  tools must never be in the list handed to `create_agent`, so they are never
  in the model's schema at all. That absence is the demo; the refusal
  transcript in `samples/README.md` is what it should produce.
- `create_agent(model="anthropic:claude-sonnet-5", tools=tools, system_prompt=...)`,
  the prompt instructing the model to pass `agent_name="agent-reader"` on every
  call.
- **Async throughout** — `async def main()` plus `asyncio.run(main())`. MCP
  tools arrive as coroutine-only `StructuredTool`s; `agent.invoke()` constructs
  fine and then fails at the first tool call.
- The API key comes from `.env.local` through `shared/envloader.py`, never a
  shell export: put `shared/` on `sys.path`, then `load_env()` and
  `require("ANTHROPIC_API_KEY")`. Verify with
  `env -u ANTHROPIC_API_KEY python agent_reader.py "Do you have Dune?"`.
- Every turn prints the tools it invoked before the answer, through
  `shared/toolvis.py`'s `show_tools` — `shared/repl.py` already does this.
- Invoked with no arguments it opens a conversation; with arguments it answers
  once and exits. Use `repl.one_shot(args, ...)`, `repl.once(agent, question)`
  and `repl.chat(agent, title=..., hints=[...])`. History carrying across turns
  is what lets one session solve several requests.

**`agent_admin.py`** — checkpoint D. `agent_reader.py` with the write tools
loaded and the admin credential presented, and nothing else different.

## Your task

Refactor LangBookStore so that its tools run on an MCP server rather than inside
the agent process, then add write tools accessible only to an administrative
agent.

`starter/test_exercise.py` is the specification. Running it reports four failing
checkpoints, each naming the tool it expects and the return shape it requires.
It needs no API key and operates on a temporary copy of the catalog.

You are not expected to write most of this by hand. Supply the specification and
the constraints below to an agent, then review the result.

**Constraints applying to every tool:**

- Parameters are typed and individually optional — `genre="Mystery"`,
  `max_price=20.0`, `count=3`. No parameter accepts a full sentence. A signature
  containing `query: str` or `user_request: str` indicates the refactor is
  incomplete.
- Tools return structured data. The model produces the prose.
- Missing records and invalid input raise `ToolError` rather than returning an
  explanatory string.
- The docstring determines whether and how the model calls the tool. State what
  is returned and enumerate valid values.
- No output goes to stdout. Diagnostics go to stderr.
- Computation is delegated to `starter/inventory.py`, which already implements
  search, scoring and the knapsack solver.

**Checkpoints.** Each represents a working state.

**A.** Implement `search_books` on the server and `agent_reader.py` as its
client, connecting over HTTP to `http://127.0.0.1:8003/mcp`. The agent connects
to a running server and does not start one. Use `create_agent` with
`anthropic:claude-sonnet-5`, load credentials through `shared/envloader.py`, and
use `shared/repl.py` so that invocation without arguments opens a conversation.
The implementation must be asynchronous throughout: MCP tools are coroutines,
and `invoke()` will construct successfully before failing at the first tool
call.

**B.** Implement `get_book`, `recommend_books` and `build_bundle`, replacing
`starter/tools/*.py`. Do not port the `_extract_*` functions; each recovers a
parameter the model supplies directly when the schema requests it.

**C.** Implement `add_book`, `update_book` and `delete_book`. Writes must persist
to disk and be visible to subsequent reads within the same process.

**D.** Restrict the write tools behind an administrative credential that appears
in no tool's input schema, so that the model can neither read nor supply it.
Over HTTP the credential arrives as a request header. Then implement
`agent_admin.py`: `agent_reader.py` with the write tools and that credential.

**Verification:**

```bash
python test_exercise.py -c A     # or B, C, D
python test_exercise.py          # all four
```

Restore the catalog between runs with `cp ../storedata.json storedata.json`.

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**Connection error** — the server is not running.

**A write succeeds but the next read misses it** — that is checkpoint C.
