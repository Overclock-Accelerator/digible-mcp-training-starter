# Sample runs

All commands are from the repo root, with the virtualenv active and
`ANTHROPIC_API_KEY` in `.env.local`. Sample 1 and the `--render-only` path need
neither servers nor a key.

The five servers are separate HTTP processes on ports 8010–8014. Samples 2–7
require them running; the agent connects to them and never spawns them.

```bash
./07-mcp-for-all-the-tokens/start_servers.sh
./07-mcp-for-all-the-tokens/stop_servers.sh
```

---

## 1. The stack — no API key needed

```bash
python 07-mcp-for-all-the-tokens/catalog.py
```

```
1. Northwind Docs       5 tools   cumulative   5   port 8010   (internal engineering documentation)
2. Helios Helpdesk     10 tools   cumulative  15   port 8011   (customer support desk)
3. Meridian CRM        20 tools   cumulative  35   port 8012   (sales and customer records)
4. Lumen Analytics     40 tools   cumulative  75   port 8013   (product analytics and BI)
5. Bastion Infra       80 tools   cumulative 155   port 8014   (cloud infrastructure platform)
```

An error here means the catalogue's self-check caught a duplicate tool name or a
drifted count; the message names which.

---

## 2. The tax probe

A prompt that calls no tool, with one server connected and then with five.
Everything is fixed except how many tool schemas were serialized into the request.

```bash
python 07-mcp-for-all-the-tokens/agent.py --probe --servers 1
python 07-mcp-for-all-the-tokens/agent.py --probe --servers 5
```

On stderr, one line each:

```
[1 servers / 5 tools]   in=1507  out=6 round_trips=1 tool_calls=0 wall=~1s probe
[5 servers / 155 tools] in=27086 out=6 round_trips=1 tool_calls=0 wall=~2s probe
```

Both answer `READY`, after the same amount of work, at eighteen times the input cost.

---

## 3. One task, one server against five

```bash
python 07-mcp-for-all-the-tokens/agent.py --task i_spaces --servers 1
python 07-mcp-for-all-the-tokens/agent.py --task i_spaces --servers 5
```

Both call `list_spaces` and report the five Northwind spaces. The tool-call
trace is identical; the token line differs, roughly 3,200 input tokens against
roughly 54,000.

---

## 4. The adversarial case

```bash
python 07-mcp-for-all-the-tokens/agent.py --task a_failover --servers 5
```

The prompt is *"I need the failover runbook for the database. Find it for me."*
There is a tool called `failover_database` on the Bastion Infra server. The
correct answer is `search_docs` on Northwind, because the request is for a
document. The trace shows `search_docs`, then a summary of NW-4471, and no
Bastion call.

---

## 5. The position control

`--reverse` registers Northwind last rather than first, ruling out list position
as the cause of the accuracy result.

```bash
python 07-mcp-for-all-the-tokens/agent.py --task a_failover --servers 5 --reverse
```

Same tool, same answer.

---

## 6. The chat loop

No arguments opens a conversation (repo convention, `shared/repl.py`). History
carries across turns and each turn prints its tool calls.

```bash
python 07-mcp-for-all-the-tokens/agent.py --servers 1     # chat with 5 tools
python 07-mcp-for-all-the-tokens/agent.py --servers 5     # chat with 155 tools
```

```bash
python 07-mcp-for-all-the-tokens/agent.py --ask "find me the docs on rate limits" --servers 1
python 07-mcp-for-all-the-tokens/agent.py --ask "find me the docs on rate limits" --servers 5
```

Observed on one run each: at 5 tools, four calls, all of them Northwind's
`search_docs` and `list_spaces`, rewording the query. At 155 tools, three calls
to **three different vendors** — Bastion's `search_documentation`, Northwind's
`search_docs`, Helios's `find_documents`.

A follow-up the model can answer from memory ("which of those is for
engineering?") prints
`(none — the model answered without calling a tool)`.

This path is a demonstration, not a measurement: single runs, no scoring. Every
number in `results/` comes from `benchmark.py`.

---

## 7. The whole sweep

```bash
python 07-mcp-for-all-the-tokens/benchmark.py --runs 1     # smoke run,  ~95 API calls, ~10 min
python 07-mcp-for-all-the-tokens/benchmark.py --runs 3     # committed,  285 API calls, ~35 min
python 07-mcp-for-all-the-tokens/benchmark.py --render-only  # re-render from results.json
```

`--render-only` rebuilds every chart and table from `results/results.json` with
no key and no network.
