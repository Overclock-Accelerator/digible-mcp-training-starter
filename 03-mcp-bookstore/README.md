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

- Run `python test_exercise.py` — it fails 4/4 and tells you what is missing.
- **A.** Put `search_books` on the server and build `agent_reader.py` to call it.
- **B.** Add `get_book`, `recommend_books`, `build_bundle`.
- **C.** Add `add_book`, `update_book`, `delete_book`.
- **D.** Gate the writes behind a credential the model cannot see, then build
  `agent_admin.py`.
- Check each with `python test_exercise.py -c A` (or `B`, `C`, `D`).

Tools take typed parameters, return data not prose, and never print to stdout.
Reset the catalog with `cp ../storedata.json storedata.json`.

## Troubleshooting

**`ModuleNotFoundError`** — run `source .venv/bin/activate` from the repo root.

**Connection error** — the server is not running.

**A write succeeds but the next read misses it** — that is checkpoint C.
