# MCP Training — starter repo

This repo holds the demos we run together and the starters for the activities
you build yourself. Each numbered folder is one segment of the session and has
its own README explaining what it is and how to run it.

An MCP server is a small program that exposes tools over a protocol, so any
client can call them — your agent, someone else's agent, or Claude Desktop.
Folders `00` through `02` show a tool moving out of an agent and into a server.
`03` and up are where you build one yourself.

Work through the folders in order.

## Prerequisites

- **Python 3.10 or newer** — check with `python3 --version`
- **An Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/)
  — needed for folders marked "key" below
- **`git`**, plus **`curl`** and **`jq`** for folder `06`
- A terminal you can open two or three windows of — most demos run a server in
  one window and an agent in another

## Setup

```bash
git clone <this repo>
cd mcp-training
./setup.sh                          # venv + pinned deps + solver tests
cp .env.local.example .env.local    # then put your ANTHROPIC_API_KEY in it
```

If `./setup.sh` ends with `10 passed, 0 failed`, your environment is good.

Run anything with the repo's own interpreter — no `activate` needed, and it
cannot pick up the wrong virtualenv:

```bash
./.venv/bin/python 01-mcp-bee/mcp_server.py      # terminal 1
./.venv/bin/python 01-mcp-bee/agent_with_mcp.py  # terminal 2
```

`.env.local` is gitignored. Every agent here loads it through
`shared/envloader.py`, so you never export anything in your shell — and you can
prove it, which is worth doing once:

```bash
env -u ANTHROPIC_API_KEY ./.venv/bin/python 01-mcp-bee/agent_with_mcp.py "..."
```

## The folders

**Demo** — we run it together and you follow along.
**Activity** — you build it, with a specification to check yourself against.

| | | Key? | What it is |
|---|---|---|---|
| `00-agent-bee` | demo | yes | A LangChain agent solving NYT Spelling Bee with a local tool. |
| `01-mcp-bee` | demo | yes | The same solver moved behind a FastMCP server, so you can diff the two agents. |
| `02-mcp-puzzlemaster` | demo | yes | Three agents sharing one server, one dictionary and one audit log. Usage graphs and CSV export. |
| `03-mcp-bookstore` | **activity** | yes | Refactor a real LangChain agent onto MCP in four checkpoints, then add authenticated writes. |
| `04-mcp-deployment` | demo | no | Deploying a local MCP server to a hosted one. An HTML page. |
| `05-mcps-for-all` | demo | no | Reaching an MCP server from Claude Desktop, without writing Python. An HTML page. |
| `06-mcp-breakdown` | **activity** | no | Take three production MCP servers apart — Zapier, Snowflake, Datadog — using a worksheet you keep. |
| `07-mcp-for-all-the-tokens` | demo | yes | What tool definitions cost in context, measured across five servers. |
| `08-mcp-vs-cli` | demo | yes | The same work through MCP tools and through a CLI, measured against each other. |
| `09-mcp-architecture` | **activity** | yes | Six agents that each reinvented the same database primitives. Count the duplication, then collapse it behind one server. |

### Deployed servers

Two servers from this course are live and public, with no sign-in. You need
nothing on your machine to call them.

| | Endpoint |
|---|---|
| PuzzleMaster | `https://mcp-puzzlemaster.fastmcp.app/mcp` |
| Digible Data | `https://mcp-digible-queries.fastmcp.app/mcp` |

`05-mcps-for-all` walks through pointing Claude Desktop at one of them.

## Troubleshooting

**`ModuleNotFoundError`** — a different virtualenv is active. Run agents with
this repo's interpreter: `./.venv/bin/python <folder>/<agent>.py`

**A tool call fails immediately** — the MCP server is not running. Most folders
need it started in its own terminal first; the folder README says which command.

**Do not upgrade `mcp`.** `requirements.txt` pins 1.29.1 because
`langchain-mcp-adapters` requires `mcp<2.0.0`. An unpinned `pip install mcp`
breaks every agent here.

## The HTML pages

Most of this repo is markdown, which GitHub renders in the browser. Four pages
are HTML instead, meant to be projected:

| Page | |
|---|---|
| `04-mcp-deployment/index.html` | Deploying an MCP server to Prefect Horizon |
| `05-mcps-for-all/index.html` | Connecting Claude Desktop to a deployed server |
| `07-mcp-for-all-the-tokens/index.html` | What ballooning tool counts cost |
| `08-mcp-vs-cli/index.html` | MCP versus the command line, measured |

GitHub will not render those — download and open them. Each is self-contained.

## License

MIT. See [LICENSE](LICENSE).
