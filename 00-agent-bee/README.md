# 00 — A LangChain agent with a local tool

**The one idea:** a Python function becomes a tool the model can call, and the
agent decides when to call it.

That is the whole folder. One agent, one tool, one file. Everything here is the
ordinary, correct way to build a tool-calling agent today.

## Setup

One virtualenv for the whole repo, created at the repo root:

```bash
cd ~/mcp-training                   # the repo root, wherever you cloned it
./setup.sh                          # venv + pinned deps + solver tests
cp .env.local.example .env.local    # then put your ANTHROPIC_API_KEY in it
```

Run any agent with the repo's own interpreter — no `activate` needed, and it
cannot pick up the wrong virtualenv:

```bash
../.venv/bin/python agent_with_mcp.py
```

Pinned on purpose. `langchain` 1.3.18 pins `langgraph>=1.2.11,<1.3.0` and
`langchain-core>=1.6.0`; upgrading any one of them independently breaks
resolution. Don't `pip install -U langchain` mid-session.

## Run it

Solve a puzzle directly:

```bash
python agent.py --letters VALIDTY --center V
```

Ask in your own words, and watch the model decide to reach for the tool:

```bash
python agent.py --question "For the Spelling Bee letters VALIDTY with center letter V, which answers are worth 10 or more points?"
```

See `samples/` for these commands with their expected output.

## What to notice

**1. The docstring and the type hints *are* the API.** Look at the `@tool`
function:

```python
@tool
def spelling_bee(letters: str, center: str) -> dict:
    """Solve a NYT Spelling Bee puzzle exhaustively and score every answer.

    Args:
        letters: The 7 puzzle letters as one string, e.g. "VALIDTY".
        center: The mandatory center letter, e.g. "V". Must be one of `letters`.
    """
```

`@tool` turns that into a JSON Schema and ships it to the model with every
request. The model never sees the function body — it sees the name, the
description, and the argument types. That is the entire contract. A vague
docstring produces a vague tool, and no amount of prompting fixes it.

**2. The agent chose to call it.** In the `--question` run nobody said "call
`spelling_bee`". The model read the question, read the schema, and decided.
The `[tool call]` / `[tool result]` lines are printed from inside the tool
itself, so you are watching the real invocation, not a log of one.

**3. The solver is deterministic; the agent is not.** `solve_spelling_bee`
always returns 34 words and 171 points for this puzzle. The prose around it
varies run to run. That split — a deterministic tool wrapped in a
non-deterministic caller — is why tool-calling works at all.

**4. `create_agent` is the current API.** Not `initialize_agent`, not
`AgentExecutor`, not `langgraph.prebuilt.create_react_agent`. That last one is
the trap: it still imports and half-works, so tutorials using it look fine
until they don't.

**5. Async from the start.** `async def main()` + `asyncio.run(...)` +
`await agent.ainvoke(...)`. Nothing here strictly requires it yet, but it costs
nothing now and it means the structure never has to change.

## The solver

`solve_spelling_bee` is copied verbatim from `../shared/solvers_reference.py`.
Rules: 4+ letters, must contain the center letter, may use only the 7 allowed
letters but may reuse them freely — hence `set(word) <= allowed`, a subset
test, not a multiset one. Scoring: a 4-letter word is **1 point flat** (not 4 —
this is the usual bug), 5+ letters score 1 point per letter, and a pangram
earns **+7** on top.

ENABLE1 gives 34 words / 171 points for VALIDTY/V. The NYT's own curated answer
for that puzzle was 21 words / 119 points. A public word list over-generates
against editorial curation; the tool is exactly right about the rules and
still disagrees with the newspaper.
