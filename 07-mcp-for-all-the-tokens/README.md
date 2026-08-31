# 07 — MCP for All the Tokens

One agent connected to five MCP servers, measuring what tool definitions cost
in context as you add more.

## Run

From the repo root, virtualenv active.

Start the five servers and leave them running:

```bash
./07-mcp-for-all-the-tokens/start_servers.sh    # ports 8010-8014
```

Then, in a second terminal:

```bash
python 07-mcp-for-all-the-tokens/agent.py --servers 1     # chat with 5 tools
python 07-mcp-for-all-the-tokens/agent.py --servers 5     # chat with 155 tools
```

Stop them when you are done:

```bash
./07-mcp-for-all-the-tokens/stop_servers.sh
```

## Prompts

Ask the same thing at both sizes and compare which tools get called:

```
find me the docs on rate limits
who is on call for the payments service?
open a ticket about the failover runbook being out of date
```

## Results

Committed in `results/`. Input tokens for a prompt that calls no tool, varying
only how many servers are connected:

| Servers | Tools | Input tokens | vs. 1 |
|---:|---:|---:|---:|
| 1 | 5 | 1,507 | 1.00x |
| 2 | 15 | 3,378 | 2.24x |
| 3 | 35 | 7,235 | 4.80x |
| 4 | 75 | 14,224 | 9.44x |
| 5 | 155 | 27,086 | 17.97x |

270 task runs, 270 correct tool selections. Across 292 tool calls, the 150
non-Northwind tools were called 0 times.

Schema size per server:

```bash
python 07-mcp-for-all-the-tokens/show_schema.py --servers 5 --weigh
```

## Troubleshooting

**`ModuleNotFoundError`** — run `source .venv/bin/activate` from the repo root.

**Connection error** — the servers are not running. Run `start_servers.sh`.

**Port already in use** — run `stop_servers.sh`, then start again.
