# 02b — PuzzleMaster Solo

One MCP server that works out which game you are playing, so the agent never
has to. A transition between 02 and 03: same three solvers, same dictionary,
routing moved to the other side of the protocol.

## Run

All commands are from the repo root, with the virtualenv active. This server
needs `ANTHROPIC_API_KEY` — the first one in the course that does.

Start it and leave it running:

```bash
python 02b-mcp-puzzlemaster-solo/mcp_server.py
```

```
[solo] loaded 172,823 words from enable1.txt in 19.5ms
[solo] classifier model: claude-sonnet-5
[solo] listening on http://127.0.0.1:8020/mcp
```

In a second terminal:

```bash
python 02b-mcp-puzzlemaster-solo/agent_solo.py
```

## The ONE idea

In `02`, `agent_puzzlemaster.py` loads three tools and the **agent's** model
picks between them. Here the server exposes **one** tool that takes plain
English, and does the picking itself:

```python
# 02 — the client chooses
MY_TOOLS = ("solve_spelling_bee", "solve_crossword_pattern", "solve_wordle")
tools = [t for t in await load_mcp_tools(session) if t.name in MY_TOOLS]

# 02b — there is nothing to choose
@mcp.tool(name="solve_puzzle")
def solve_puzzle_tool(agent_name: str, puzzle: str) -> dict:
    route = classify(puzzle)        # a Claude call, inside the server
    ...                             # then dispatch to the same three solvers
```

Run the same three prompts through both folders and watch the trace:

| prompt | 02 calls | 02b calls |
|---|---|---|
| `today's bee is VALIDTY, V in the middle` | `solve_spelling_bee(...)` | `solve_puzzle(...)` |
| `what fits C_O__W_RD?` | `solve_crossword_pattern(...)` | `solve_puzzle(...)` |
| `CRANE gave me green, yellow, then three blacks` | `solve_wordle(...)` | `solve_puzzle(...)` |

Same answers — 34 words / 171 points / VALIDITY, one match CROSSWORD, 34
candidates. In 02 the trace shows *which* game was detected. In 02b it never
does, because the client was never told.

## What you gain

**A door anyone can open.** `solve_puzzle("what fits C_O__W_RD?")` needs no
knowledge of the three games, no argument extraction, and no model on the
client side at all. A shell script can call it.

**A four-sentence agent.** `agent_solo.py`'s system prompt is four sentences
next to `agent_puzzlemaster.py`'s thirty-line routing rulebook, because there
is nothing left to teach it.

**One place to fix a misroute.** Every client gets the fix at once, without
redeploying anything.

## What you lose — say all four out loud

**Latency, by two to three orders of magnitude.** The audit table times the two
halves separately, and the gap is the headline:

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

Routing is now a network round trip to a language model. Solving is a list
comprehension over 172k strings. **The tool got ~300x slower and none of it
went into the answer.** (Expect the very first call after startup to be slower
still — 15s or so — while the HTTP client warms up. Ignore it; run twice.) In
02 that same routing cost was paid too, but inside a model call the agent was
already making, so it was free.

**Non-determinism, including in the error path.** Ask for a bee with three
letters and the server may route it to `spelling_bee` and return the solver's
deterministic `need exactly 7 distinct letters, got 3` — or it may route to
`unknown` and return a sentence the model wrote just now. Both are correct;
they are not the same string, and neither is stable across runs. Anything
downstream that matches on error text will eventually break.

**A tool description that lies by omission.** The schema says `puzzle: str`.
Nothing in it tells you three games are supported, or which ones. The model on
the other side gets no signal about what will and will not work until it fails.

**Blame moves.** In 02 a misroute is visible in the trace and fixable in the
agent's prompt. Here it is invisible, and only `routing_log` can find it:

```bash
python 02b-mcp-puzzlemaster-solo/monitor.py --log
```

```
ok  wordle        3390ms  'I played CRANE and got green, yellow, then t'
      -> Single 5-letter guess CRANE with color feedback maps to wordle.
```

The `why` column is the classifier's own stated reason, recorded at decision
time. Without it, a server-side misroute is unfalsifiable.

## How the classifier is pinned down

The routing call uses **structured outputs** — the response is constrained to a
JSON Schema, so it parses or it errors:

```python
response = _client.messages.create(
    model="claude-sonnet-5",
    output_config={"format": {"type": "json_schema", "schema": ROUTE_SCHEMA}},
    ...
)
```

There is no "sometimes it wrapped the JSON in a code fence" branch to write.
That guarantee is what makes it safe to put a model call inside a tool at all.

Two details worth pausing on:

- **`stop_reason` is checked before `content` is read.** A refusal returns HTTP
  200 with an empty content list; indexing it blind is the classic crash.
- **The prompt spells out `gybbb`.** Without an explicit "green→g, yellow→y,
  black→b, one character per letter" rule, the model returns
  `["green","yellow","black","black","black"]` — schema-valid and useless. The
  schema constrains *shape*, never *meaning*.

## Which one should you build?

Neither is the answer; the question is where you want the intelligence.

| | 02 — client routes | 02b — server routes |
|---|---|---|
| Tool surface | 3 typed tools | 1 tool taking English |
| Who interprets | the agent's model | the server's model |
| Visible in trace | yes | no |
| Client needs a model | yes | no |
| Added latency | none (same model call) | a full round trip |
| Misroute is | an agent bug | a server bug |

Typed tools where the caller already knows what it wants; a natural-language
front door where it doesn't. `03-mcp-bookstore` asks you to make this call
yourself — that folder's ONE idea is that moving a tool behind MCP is a
redesign, not a port, and this is the redesign in miniature.

## Troubleshooting

**`ANTHROPIC_API_KEY is not set`** — unlike 01 and 02, this *server* needs the
key. Put it in `.env.local` at the repo root; it fails at startup, on purpose.

**`WinError 10048` / `address already in use`** — a server is already on 8020.
Stop it, or pass `--port`.

**`UnicodeEncodeError: 'charmap' codec`** — Windows console only. Set
`PYTHONIOENCODING=utf-8`.

**Every call routes to `unknown`** — read the `why` column in `monitor.py
--log`. The classifier says what it thought was missing.
