# Sample invocations

Copy-pasteable, with what you should see. Run from inside
`07-mcp-for-all-the-tokens/` with the repo virtualenv active and
`ANTHROPIC_API_KEY` in `../.env.local`.

**Start the servers first.** They are five separate HTTP processes on ports
8010–8014; the agent connects to them and never spawns them.

```bash
./start_servers.sh      # samples 2-7 need this
./stop_servers.sh       # when you are done
```

Samples 1 and the `--render-only` path need neither servers nor an API key.

---

## 1. What the stack looks like — no API key needed

```bash
python catalog.py
```

Expected:

```
1. Northwind Docs       5 tools   cumulative   5   (internal engineering documentation)
2. Helios Helpdesk     10 tools   cumulative  15   (customer support desk)
3. Meridian CRM        20 tools   cumulative  35   (sales and customer records)
4. Lumen Analytics     40 tools   cumulative  75   (product analytics and BI)
5. Bastion Infra       80 tools   cumulative 155   (cloud infrastructure platform)
```

If this errors, the catalogue's self-check caught a duplicate tool name or a
drifted count — the message says which.

---

## 2. The tax probe — the single most useful command in the folder

A prompt that calls no tool at all, with one server connected and then with five.
Everything is fixed except how many tool schemas were serialized into the request.

```bash
python agent.py --probe --servers 1
python agent.py --probe --servers 5
```

Expected on stderr, one line each:

```
[1 servers / 5 tools]   in=1507  out=6 round_trips=1 tool_calls=0 wall=~1s probe
[5 servers / 155 tools] in=27086 out=6 round_trips=1 tool_calls=0 wall=~2s probe
```

Both answer `READY`. Both did the same amount of work. One cost eighteen times
as much. **Run these two back to back in the room** — the whole folder is in
that pair of numbers.

---

## 3. One task, one server vs. five

The same request, the same correct answer, the same single tool call.

```bash
python agent.py --task i_spaces --servers 1
python agent.py --task i_spaces --servers 5
```

Expected: both call `list_spaces` and report the five Northwind spaces. The
tool-call trace is identical. Only the token line differs — roughly 3,200 input
tokens against roughly 54,000.

---

## 4. The adversarial case — the one built to break

```bash
python agent.py --task a_failover --servers 5
```

The prompt is *"I need the failover runbook for the database. Find it for me."*
There is a tool called `failover_database` on the Bastion Infra server. The
correct answer is `search_docs` on Northwind, because the user asked for a
document.

Expected: `search_docs`, then a summary of NW-4471. Watch the trace, not the
prose — the interesting question is which tool got called first, and whether
anything from Bastion got touched at all.

---

## 5. The position control

The right answers live on the server registered first. That is a selection bias
worth ruling out, so `--reverse` registers Northwind last instead.

```bash
python agent.py --task a_failover --servers 5 --reverse
```

Expected: same tool, same answer. If this diverged from sample 4, the accuracy
result would be about list position rather than about descriptions.

---

## 6. Talk to it — the one to do live

Running the agent with **no arguments opens a conversation** (repo convention,
`shared/repl.py`). History carries across turns and each turn prints its tool
calls.

```bash
python agent.py --servers 1     # chat with 5 tools
python agent.py --servers 5     # chat with 155 tools
```

Then ask the same genuinely ambiguous thing in both, and watch the tool-call
line rather than the prose. Something with no answer in the fixtures works best
— take a suggestion from the room, or use:

```bash
python agent.py --ask "find me the docs on rate limits" --servers 1
python agent.py --ask "find me the docs on rate limits" --servers 5
```

Observed on one run each: at 5 tools it made four calls, all of them Northwind's
`search_docs` and `list_spaces`, rewording the query. At 155 tools it made three
calls to **three different vendors** — Bastion's `search_documentation`,
Northwind's `search_docs`, Helios's `find_documents`.

Worth pointing at in the third turn of a chat: ask a follow-up the model can
answer from memory ("which of those is for engineering?") and the trace prints
`(none — the model answered without calling a tool)`.

**This path is a demonstration, never a measurement.** Single runs, no scoring.
Every number in `results/` comes from `benchmark.py`.

---

## 7. The whole sweep

```bash
python benchmark.py --runs 1     # smoke run,  ~95 API calls, ~10 min
python benchmark.py --runs 3     # committed,  285 API calls, ~35 min
python benchmark.py --render-only  # re-render from committed results.json, no API calls
```

`--render-only` is the one to reach for in a session: it rebuilds every chart
and table from `results/results.json` with no key and no network.
