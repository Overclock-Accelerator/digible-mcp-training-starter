# 03 — Bookstore

Move a working LangChain agent onto an MCP server, then add write tools only an
admin agent can use.

## Run

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
