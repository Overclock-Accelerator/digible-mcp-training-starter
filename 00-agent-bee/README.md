# 00 — Agent Bee

A LangChain agent with the Spelling Bee solver as a local `@tool`.

## Run

All commands are from the repo root, with the virtualenv active.

```bash
python 00-agent-bee/agent.py --letters VALIDTY --center V
python 00-agent-bee/agent.py --letters CAPITOL --center C
```

VALIDTY returns 34 words, 171 points, pangram VALIDITY. CAPITOL returns 136
words, 737 points.

The same puzzle stated as a question:

```bash
python 00-agent-bee/agent.py --question "For the Spelling Bee letters VALIDTY with center letter V, which answers are worth 10 or more points?"
```

Two words — VALIDITY at 15 and ADDITIVITY at 10. Every invocation prints a
`[tool call]` / `[tool result]` pair before the answer.

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**`error: ANTHROPIC_API_KEY is not set`** — put your key in `.env.local` at the
repo root. Copy `.env.local.example` if it is not there.

**`error: --center 'Z' must be one of the letters 'VALIDTY'`** — the center
letter must be one of the seven.
