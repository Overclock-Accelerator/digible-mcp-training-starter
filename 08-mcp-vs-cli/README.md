# 08 — MCP vs. CLI

The same solvers exposed two ways — as MCP tools and as a CLI the agent shells
out to — measured against each other.

## Run

From the repo root, virtualenv active. Generate the padding commands once:

```bash
python 08-mcp-vs-cli/cli/make_pad.py
```

Confirm both sides share identical solver code:

```bash
python 08-mcp-vs-cli/verify_solvers.py
```

Use the CLI directly:

```bash
python 08-mcp-vs-cli/cli/puzzle bee --letters VALIDTY --center V
python 08-mcp-vs-cli/cli/puzzle bee --letters VALIDTY --center V --json \
  | jq '[.words[] | select(.word|length >= 5)] | length'
```

Run either agent on one task:

```bash
python 08-mcp-vs-cli/agent_mcp.py --task solve --tools 3
python 08-mcp-vs-cli/agent_mcp.py --task solve --tools 40
python 08-mcp-vs-cli/agent_cli.py --task solve --capabilities 3
python 08-mcp-vs-cli/agent_cli.py --task solve --capabilities 40
```

Compare on the aggregate task:

```bash
python 08-mcp-vs-cli/agent_mcp.py --task aggregate
python 08-mcp-vs-cli/agent_cli.py --task aggregate
python 08-mcp-vs-cli/agent_cli.py --task aggregate --brief
```

## Results

Committed in `results/`. 95 runs, all correct, `claude-sonnet-5`.

Input tokens for the same task, varying only how many capabilities exist:

| Capabilities | MCP | CLI |
|---:|---:|---:|
| 3 | 3,344 | 2,220 |
| 15 | 7,629 | 2,220 |
| 40 | 16,320 | 2,217 |

Aggregate task — "how many answers are five letters or longer?", answer 24:

| Arm | Input | Output | Result chars into context |
|---|---:|---:|---:|
| MCP | 3,345 | 447 | 1,665 |
| CLI | 4,240 | 180 | 2,005 |
| CLI, schema known | 1,449 | 96 | 2 |

Redraw the charts, or re-run:

```bash
python 08-mcp-vs-cli/benchmark.py --render-only
python 08-mcp-vs-cli/benchmark.py --runs 5        # ~12 min, ~95 API calls
```

## Troubleshooting

**`ModuleNotFoundError`** — run `source .venv/bin/activate` from the repo root.

**`jq: command not found`** — install `jq`, or drop the pipe.

**`puzzle: command not found`** — run `python 08-mcp-vs-cli/cli/make_pad.py` first.
