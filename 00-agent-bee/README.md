# 00 — Agent Bee

A LangChain agent with the Spelling Bee solver as a local `@tool`.

## Files

| | |
|---|---|
| `agent.py` | The agent and the solver, in one file |
| `samples/` | Captured runs |

## Run it

All commands are from the repo root, with the virtualenv active.

Solve a puzzle directly:

```bash
python 00-agent-bee/agent.py --letters VALIDTY --center V
```

Ask in your own words instead:

```bash
python 00-agent-bee/agent.py --question "For the Spelling Bee letters VALIDTY with center letter V, which answers are worth 10 or more points?"
```

Both print a `[tool call]` / `[tool result]` pair before the answer.

## Sample prompts

| what you run | what you get back |
|---|---|
| `--letters VALIDTY --center V` | 34 words, 171 points, pangram VALIDITY |
| `--letters CAPITOL --center C` | 136 words, 737 points |
| `--question "…which answers are worth 10 or more points?"` | two words — VALIDITY at 15, ADDITIVITY at 10 |

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**`error: ANTHROPIC_API_KEY is not set`** — put your key in `.env.local` at the
repo root. Copy `.env.local.example` if you have not already.

**`error: --center 'Z' must be one of the letters 'VALIDTY'`** — the center
letter has to be one of the seven.
