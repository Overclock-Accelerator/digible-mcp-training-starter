# Sample runs

Commands are from the repo root, with the virtualenv active. Sections 1–4 need
`ANTHROPIC_API_KEY` — including the **server**, which is new in this folder.
Section 5 needs no key and no network.

Start the server first, in its own terminal, and watch that window:

```bash
python 02b-mcp-puzzlemaster-solo/mcp_server.py
```

## 1. Three games, one tool call

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py \
  --ask "today's bee is VALIDTY, V in the middle"
```

```
  1. solve_puzzle(agent_name="agent-solo", puzzle="today's bee is VALIDTY, V in the mid...")
     → {game: "spelling_bee", why: "Seven letters wi…", arguments: {…}, result: {…}}
```

**34 words, 171 points, pangram VALIDITY** — same answer as `02`.

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py --ask "what fits C_O__W_RD?"
```

```
  1. solve_puzzle(agent_name="agent-solo", puzzle="what fits C_O__W_RD?")
     → {game: "crossword", why: "Letters interlea…", arguments: {…}, result: {…}}
```

One match, **CROSSWORD**.

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py \
  --ask "I played CRANE and got green, yellow, then three blacks"
```

```
  1. solve_puzzle(agent_name="agent-solo", puzzle="I played CRANE and got green, yellow...")
     → {game: "wordle", why: "Single 5-letter …", arguments: {…}, result: {…}}
```

**34 candidates**, and the server extracted `feedback: ["gybbb"]` from the
colour words.

**The line to point at:** the tool call is `solve_puzzle(...)` all three times.
Run the same three prompts against `02/agent_puzzlemaster.py` and the trace
names a different tool each time. Same answers, different place to look.

## 2. Compare the two folders side by side

```bash
# terminal 1
python 02-mcp-puzzlemaster/mcp_server.py
# terminal 2
python 02b-mcp-puzzlemaster-solo/mcp_server.py

python 02-mcp-puzzlemaster/agent_puzzlemaster.py --ask "what fits C_O__W_RD?"
python 02b-mcp-puzzlemaster-solo/agent_solo.py    --ask "what fits C_O__W_RD?"
```

```
02   1. solve_crossword_pattern(agent_name="agent-puzzlemaster", pattern="C_O__W_RD")
02b  1. solve_puzzle(agent_name="agent-solo", puzzle="what fits C_O__W_RD?")
```

Also diff the two system prompts — `agent_puzzlemaster.py` spends about thirty
lines teaching the model to tell three games apart; `agent_solo.py` spends four
sentences, because there is nothing to tell apart.

## 3. What it costs — the number to say out loud

```bash
python 02b-mcp-puzzlemaster-solo/monitor.py --cost
```

```
game           calls     route    solve    ratio
------------------------------------------------
wordle             1    3268ms     17ms     192x
spelling_bee       1    2809ms      7ms     401x
crossword          1    3982ms      8ms     498x
------------------------------------------------
all                3    3353ms     11ms     314x
```

Deciding which game it is takes ~300x longer than answering it. The first call
after startup is slower still (~15s) while the HTTP client warms up — run twice
before quoting a number.

## 4. A failing call, and why the error is different now

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py --ask "I am playing sudoku, top row 5 3 _ _ 7"
```

The server routes to `unknown` and raises:

```
ToolError: could not tell which puzzle this is — Sudoku is not a supported
word puzzle (spelling bee, crossword, or wordle).
```

That sentence was written by a model, at request time. Ask for a three-letter
bee and you may get the solver's deterministic message instead:

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py --ask "the bee is ABC, A in the middle"
```

```
ToolError: need exactly 7 distinct letters, got 3
```

**Both are correct and the same input can produce either**, depending on
whether the classifier routed to `spelling_bee` (deterministic solver error) or
to `unknown` (model-written sentence). In `02` this input always produced the
first message. Anything downstream matching on error text will break here.

## 5. Read the routing decisions — no API key

```bash
python 02b-mcp-puzzlemaster-solo/monitor.py --log --limit 3
```

```
Last 3 routing decision(s)

ok  wordle        3268ms  'I played CRANE and got green, yellow, then t'
      -> Single 5-letter guess CRANE with colour feedback described as green, yellow, then three blacks maps to wordle.
ok  crossword     3982ms  'what fits C_O__W_RD?'
      -> Letters interleaved with underscore blanks indicate a crossword pattern.
ok  spelling_bee  2809ms  "today's bee is VALIDTY, V in the middle"
      -> Seven letters with a specified middle letter indicates spelling_bee.
```

The `why` column is the classifier's own reason, recorded at decision time.
This table is the **only** place a server-side misroute is visible — the agent
never learned which game was chosen, so its trace cannot show one.

Failures land here too, one row each, with the game the server had settled on
before it failed:

```bash
sqlite3 02b-mcp-puzzlemaster-solo/usage.db \
  "SELECT game, ok, why FROM invocations WHERE ok=0;"
```
