# MCP Training — starter repo

This repository holds demonstrations for the Digible AI Engineering MCP
Training. Each numbered folder is one segment of the session and has its own
README explaining what it is and how to run it.

## Prerequisites

- **Python 3.10 or newer** — check with `python3 --version`
- **An Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/)
  — needed for folders marked "key" below
- **`git`**, plus **`curl`** and **`jq`** for folder `06`

## Setup

```bash
git clone https://github.com/Overclock-Accelerator/digible-mcp-training-starter.git
cd digible-mcp-training-starter
./setup.sh
cp .env.local.example .env.local
```

Then open `.env.local` and paste in your Anthropic API key.

`setup.sh` should end with `10 passed, 0 failed`. If it does, you are set up.

Each folder's README tells you what to run there.

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
