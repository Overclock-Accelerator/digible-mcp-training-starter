# MCP Training — starter repo

This repository holds demonstrations for the Digible AI Engineering MCP
Training. Each numbered folder is one segment of the session and has its own
README explaining what it is and how to run it.

## Prerequisites

- **Python 3.10 or newer** — check with `python3 --version`
- **An Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/),
  for the folders marked "key" below
- **`git`**, plus **`curl`** and **`jq`** for folder `06`

## Setup

```bash
git clone https://github.com/Overclock-Accelerator/digible-mcp-training-starter.git
cd digible-mcp-training-starter
./setup.sh
source .venv/bin/activate
cp .env.local.example .env.local
```

Add the Anthropic API key to `.env.local`. `setup.sh` runs the solver tests,
which report `10 passed, 0 failed`.

## The folders

**Demo** — run during the session. **Activity** — built against a specification.

| | | Key? | What it is |
|---|---|---|---|
| `00-agent-bee` | demo | yes | A LangChain agent solving NYT Spelling Bee with a local tool. |
| `01-mcp-bee` | demo | yes | The same solver behind a FastMCP server, alongside the local-tool agent. |
| `02-mcp-puzzlemaster` | demo | yes | Three agents sharing one server, one dictionary and one audit log. Usage graphs and CSV export. Plus a fourth agent holding all three tools, routing between them itself. |
| `02b-mcp-puzzlemaster-solo` | demo | yes | The same solvers behind one tool that takes plain English — the *server* calls Claude to work out which game it is. Client-side vs server-side routing, both halves timed. |
| `03-mcp-bookstore` | **activity** | yes | Refactor a LangChain agent onto MCP in four checkpoints, then add authenticated writes. |
| `04-mcp-deployment` | demo | no | Deploying a local MCP server to a hosted one. An HTML page. |
| `05-mcps-for-all` | demo | no | Reaching an MCP server from Claude Desktop without writing Python. An HTML page. |
| `06-mcp-breakdown` | **activity** | no | Three production MCP servers — Zapier, Snowflake, Datadog — examined against a worksheet. |
| `07-mcp-for-all-the-tokens` | demo | yes | What tool definitions cost in context, measured across five servers. |
| `08-mcp-vs-cli` | demo | yes | The same work through MCP tools and through a CLI, measured against each other. |
| `09-mcp-architecture` | **activity** | yes | Six agents implementing the same database primitives independently. Measure the duplication, then consolidate it behind one server. |

### Deployed servers

Two servers from this course are public and require no sign-in.

| | Endpoint |
|---|---|
| PuzzleMaster | `https://mcp-puzzlemaster.fastmcp.app/mcp` |
| Digible Data | `https://mcp-digible-queries.fastmcp.app/mcp` |

`05-mcps-for-all` documents connecting Claude Desktop to one of them.

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**A tool call fails immediately** — the MCP server is not running. Most folders
require it started in its own terminal first; the folder README names the command.

**Do not upgrade `mcp`.** `requirements.txt` pins 1.29.1 because
`langchain-mcp-adapters` requires `mcp<2.0.0`. An unpinned `pip install mcp`
breaks every agent here.

## License

MIT. See [LICENSE](LICENSE).
