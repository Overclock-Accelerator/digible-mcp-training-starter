# 01 — MCP Bee

The same Spelling Bee solver, once as a local tool and once behind an MCP
server.

## Files

| | |
|---|---|
| `agent_with_tool.py` | Agent with the solver as a local `@tool` |
| `mcp_server.py` | The solver as an MCP server |
| `agent_with_mcp.py` | The same agent, calling the server instead |
| `samples/` | Captured runs |

## Run it

All commands are from the repo root, with the virtualenv active.

Start the server and leave it running:

```bash
python 01-mcp-bee/mcp_server.py
```

In a second terminal, run either agent:

```bash
python 01-mcp-bee/agent_with_tool.py
python 01-mcp-bee/agent_with_mcp.py
```

Both open a chat. Try:

```
today's bee is VALIDTY, V in the middle
now LAMPYRD with Y in the centre
which one had more words?
```

Both answer 34 words, 171 points, pangram VALIDITY.

## Compare them

```bash
diff 01-mcp-bee/agent_with_tool.py 01-mcp-bee/agent_with_mcp.py
```

```bash
diff <(sed -n '/^def load_words/,/^    }$/p' 01-mcp-bee/agent_with_tool.py) \
     <(sed -n '/^def load_words/,/^    }$/p' 01-mcp-bee/mcp_server.py)
```

The second prints nothing.

## Inspect the server on its own

```bash
fastmcp dev inspector 01-mcp-bee/mcp_server.py
```

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**Connection error from `agent_with_mcp.py`** — the server is not running.
Start it in another terminal first.
