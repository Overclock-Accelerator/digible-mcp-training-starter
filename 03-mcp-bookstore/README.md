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

You are refactoring LangBookStore so its three tools live on an MCP server
instead of inside the agent process, then adding write tools that only an admin
agent can reach.

Start by reading `starter/test_exercise.py`. It is the specification: run it and
all four checkpoints fail, each naming the tool it expected and the shape it
wanted back. It needs no API key and runs against a throwaway copy of the
catalog, so you can run it as often as you like.

You are not expected to hand-write most of this. Prompt an agent with the
specification and the constraints below, then read what comes back and decide
whether it is right.

**Constraints that apply to every tool you write:**

- Parameters are typed and individually optional — `genre="Mystery"`,
  `max_price=20.0`, `count=3`. No tool takes a whole sentence. If a signature
  has `query: str` or `user_request: str` in it, the refactor has not happened.
- Tools return structured data. The model writes the prose.
- Not-found and invalid input raise `ToolError`, they do not return an apology
  string.
- The docstring is what the model reads to decide whether to call the tool, so
  say what comes back and enumerate valid values.
- Nothing prints to stdout. Diagnostics go to stderr.
- Call into `starter/inventory.py` for the actual work — the search, scoring and
  knapsack are already written and worth keeping.

**The four checkpoints.** Each is a working state; stop at any of them and you
have something that runs.

**A** — Implement `search_books` on the server, and build `agent_reader.py` to
call it over HTTP at `http://127.0.0.1:8003/mcp`. The agent connects to a server
you started; it must not spawn one. Use `create_agent` with
`anthropic:claude-sonnet-5`, load the key through `shared/envloader.py`, and use
`shared/repl.py` so no arguments opens a conversation. Async throughout — MCP
tools are coroutine-only, and `invoke()` will construct fine then fail the moment
a tool is called.

**B** — Add `get_book`, `recommend_books` and `build_bundle`. These replace
`starter/tools/*.py`. Read those first, but do not port their `_extract_*`
functions — each one recovers a parameter the model will pass you directly if
the schema asks for it.

**C** — Add `add_book`, `update_book` and `delete_book`. Writes must hit disk and
be visible to the next read in the same process.

**D** — Gate the three write tools behind an admin credential that appears in no
tool's input schema, so the model cannot see it, set it or invent it. Over HTTP
it arrives as a request header. Then create `agent_admin.py`: `agent_reader.py`
plus the write tools and that credential.

**Check each one:**

```bash
python test_exercise.py -c A     # or B, C, D
python test_exercise.py          # all four
```

Reset the catalog between runs with `cp ../storedata.json storedata.json`.

## Troubleshooting

**`ModuleNotFoundError`** — run `source .venv/bin/activate` from the repo root.

**Connection error** — the server is not running.

**A write succeeds but the next read misses it** — that is checkpoint C.
