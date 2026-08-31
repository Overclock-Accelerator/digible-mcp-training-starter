# MCP Training — starter repo

Everything you need for the session: the demos we run together, and the starters
for the parts you build yourself. Clone it, run `./setup.sh`, and you are ready.

Last session's lesson was that tools make agents deterministic. This session asks
what happens when the tools stop living inside one agent.

## The argument, in three moves

**Centralize.** A tool defined inside an agent belongs to that agent. Every new
consumer reimplements it, and the copies drift. Moving the tool behind an MCP
server means one implementation, many clients.

**Monitor.** Once every call goes through one place, you can count them, attribute
them, and export them. You cannot instrument what is scattered across six
codebases.

**Democratize.** An MCP server is not a Python import, so reaching it does not
require being able to write Python. The same server a developer wires into an
agent, a non-engineer reaches from Claude Desktop.

Each folder makes exactly one of these concrete, and the argument is cumulative —
`01` deliberately does not justify itself until `02`.

## Prerequisites

- **Python 3.10 or newer.** `python3 --version` to check.
- **An Anthropic API key**, for the folders that actually run a model. Get one at
  [console.anthropic.com](https://console.anthropic.com/). Several folders need
  no key at all — they are marked below.
- **`git`, `curl`, `jq`** — only `06` needs `curl` and `jq`.
- A terminal you are comfortable opening three windows of. Most of these demos
  are a server in one window and an agent in another, and seeing both at once is
  the point.

No accounts, no signups, no Node, no Docker.

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

**Demo** means we run it together and you follow along. **Activity** means you
build it, with a specification to check yourself against.

| | | Key? | What it is |
|---|---|---|---|
| `00-agent-bee` | demo | yes | A LangChain agent solving NYT Spelling Bee with a local tool. The "before" — this is good code, and nothing is wrong with it yet. |
| `01-mcp-bee` | demo | yes | The same solver moved behind a FastMCP server. Three files, diffable side by side. The solver body is byte-identical; only the seam moves. |
| `02-mcp-puzzlemaster` | demo | yes | Three agents — bee, crossword, wordle — sharing one server, one dictionary, one audit log. Usage graphs by agent and by tool, plus CSV export. |
| `03-mcp-bookstore` | **activity** | yes | Refactor a real LangChain agent onto MCP yourself, in four checkpoints, then add writes an agent is structurally unable to perform. The hands-on hour. |
| `04-mcp-deployment` | demo | no | Taking a local MCP server to a hosted one, and the six things that broke. A single page — open it in a browser. |
| `05-mcps-for-all` | demo | no | Reaching an MCP server without writing any Python, from Claude Desktop. A single page — open it in a browser. |
| `06-mcp-breakdown` | **activity** | no | Take three real production MCP servers apart — Zapier, Snowflake, Datadog — and find out how little of one you are allowed to read. You keep the worksheet. |
| `07-mcp-for-all-the-tokens` | demo | yes | What tool definitions cost in context, measured. Committed results, so the numbers are there whether or not you re-run the benchmark. |
| `08-mcp-vs-cli` | demo | yes | The same work done through MCP tools and through a CLI the agent shells out to, measured against each other. |
| `09-alt-mcp-query-sprawl` | **activity** | yes | Six agents that each independently reinvented the same six database primitives. Count the duplication, then collapse it behind one server. |

Run them in order. `04` and `05` are HTML pages — open them straight from disk;
they make no network requests.

### Deployed servers

Two servers from this course are live, public, and reachable with **no sign-in**.
Nothing on your machine is needed to talk to them.

| | Endpoint |
|---|---|
| PuzzleMaster | `https://mcp-puzzlemaster.fastmcp.app/mcp` |
| Digible Metrics | `https://mcp-digible-metrics.fastmcp.app/mcp` |

`05-mcps-for-all` walks through pointing Claude Desktop at the first one.

## Two things that will bite you

**Pin `mcp`.** PyPI's latest is 2.1.1, but `langchain-mcp-adapters` requires
`mcp<2.0.0`. `requirements.txt` pins 1.29.1. An unpinned `pip install mcp`
breaks every agent here.

**Everything is async.** MCP tools arrive as coroutines with no synchronous
counterpart. `agent.invoke()` will construct without complaint and then fail the
instant the model actually calls a tool. Use `ainvoke`.

## A note on the word list

All solvers read `shared/data/enable1.txt` — ENABLE1, 172,823 words, public
domain, committed here so the session never depends on the network. It is not
NYT's list, and it cannot be. Against the real 2026-08-28 puzzle it finds 34
words for 171 points where NYT accepted 21 for 119.

That gap is worth sitting with. The solver is not wrong; it is answering a
different question than the editor was. Deterministic tools give you exactly what
you asked for, which is not always the same as what you wanted.

## The HTML pages

Every README and results file also exists as a self-contained HTML page next to
it — `00-agent-bee/README.md` and `00-agent-bee/README.html`, and so on. The HTML
is what gets projected: same content, legible at the back of a room, dark-mode
aware, and it opens straight from disk with no network.

**The `.md` files are the source. The `.html` files are generated output.** If you
edit a markdown file, regenerate:

```bash
./.venv/bin/python shared/render_report.py --all          # every page
./.venv/bin/python shared/render_report.py --list         # which files convert
```

Not converted, on purpose: `06-mcp-breakdown/WORKSHEET.md`, because you fill it
in by hand and markdown is the right format for that.

## License

MIT. See [LICENSE](LICENSE).
