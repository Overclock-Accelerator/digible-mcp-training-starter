# 07 — MCP for all the tokens: what five servers cost one agent

**The one idea:** every tool description is text in the model's context on **every turn**, so connecting a fifth MCP server is not a one-time cost — it is a permanent per-request tax, paid whether the agent uses those tools or not.

The MCP-vs-CLI folder in this repo measured that tax on one server. This folder is the multi-server sequel: five vendors, 155 tools, and the second question that folder could not answer — **does the agent also start picking the wrong tool?**

Both halves are measured. Nothing here is estimated: LangChain surfaces the Anthropic API's own `usage_metadata` on every AI message, and `metrics.py` sums it across the whole trajectory.

**Results generated 2026-08-31 (UTC) with `anthropic:claude-sonnet-5`, 3 runs per cell, 285 API calls total.** Re-running will move output tokens and wall clock a little; input tokens will not move at all.

**The two headline numbers:** ~180 input tokens per tool per request, and **270/270 correct tool selections** — including at 155 tools, on adversarial prompts, with the correct tools registered last. The cost of over-connecting servers is tokens, not correctness.

## The scenario

A company that said yes to five vendors. Each one ships an MCP server, and each one is individually reasonable.

| # | vendor | domain | tools | cumulative |
|---:|---|---|---:|---:|
| 1 | Northwind Docs | internal engineering documentation | 5 | 5 |
| 2 | Helios Helpdesk | customer support desk | 10 | 15 |
| 3 | Meridian CRM | sales and customer records | 20 | 35 |
| 4 | Lumen Analytics | product analytics and BI | 40 | 75 |
| 5 | Bastion Infra | cloud infrastructure platform | 80 | 155 |

One agent connects to a growing prefix of that list — server 1, then 1+2, then 1+2+3 — via `MultiServerMCPClient`. The agent, the model and the prompts never change. The only variable is how many vendors are plugged in.

**The names collide, because real vendors do not coordinate.** Five teams independently solving "let the agent find a document" ship `search_docs`, `find_documents`, `lookup_document`, `query_knowledge_base` and `search_documentation`. Twenty of the 155 tools are deliberate near-duplicates of Northwind's five, one per rival server:

| Northwind (correct) | Helios | Meridian | Lumen | Bastion |
|---|---|---|---|---|
| `search_docs` | `find_documents` | `lookup_document` | `query_knowledge_base` | `search_documentation` |
| `get_doc` | `read_document` | `fetch_document` | `get_document_content` | `retrieve_doc` |
| `create_doc` | `create_page` | `new_document` | `create_doc_draft` | `publish_doc` |
| `list_spaces` | `list_workspaces` | `list_projects` | `list_namespaces` | `list_doc_spaces` |
| `get_doc_history` | `get_revision_history` | `document_history` | `get_page_versions` | `list_doc_revisions` |

Also planted, because the brief asked for it: `create_ticket` (Helios), `open_issue` (Meridian) and `file_bug` (Bastion) — three servers, three names, one idea.

## Run it

The five servers are **separate long-running processes over HTTP**, on ports 8010–8014. Nothing spawns them: you start them, and the agent connects by URL. That is the point — five vendors really is five processes, and you can watch a call land in one vendor's window while the conversation happens in another.

**Terminal 1 — the servers:**

```bash
cd 07-mcp-for-all-the-tokens
./start_servers.sh          # all five, logs to servers/logs/
tail -f servers/logs/bastion-infra.log    # watch calls arrive
./stop_servers.sh           # when you are done
```

Or run one by hand in its own window, which is better if you only care about two of them:

```bash
python servers/server.py --server northwind-docs   # http://127.0.0.1:8010/mcp
python servers/server.py --server bastion-infra    # http://127.0.0.1:8014/mcp
```

**Terminal 2 — the agent.** Needs `ANTHROPIC_API_KEY` in `../.env.local`:

```bash
python catalog.py                    # the stack + ports, no API key, no servers needed
python show_schema.py --servers 5 --weigh   # what the tool block weighs, no API key
python benchmark.py --runs 3         # the full sweep: 285 API calls, ~45 min
python benchmark.py --render-only    # re-render every chart from the committed JSON, offline
```

If the servers are not up, every command that needs them exits immediately naming the ports and the start script rather than raising a stack trace.

Single cells, for poking:

```bash
python agent.py --probe --servers 1        # 1,507 input tokens
python agent.py --probe --servers 5        # 27,086 input tokens — same answer
python agent.py --task a_failover --servers 5   # one scored task, then exit
```

### Talk to it — the demo worth doing live

Per the repo convention, **running the agent with no arguments opens a conversation**:

```bash
python agent.py --servers 1     # chat with 5 tools
python agent.py --servers 5     # chat with 155 tools
python agent.py --ask "find me the docs on rate limits"   # one question, then exit
```

Run the same ambiguous request against both and watch the tool-call line. That is a better demo than any table on this page, and it lets the room supply the request.

> **The chat loop is for demonstration, not measurement.** Every number in `results/` comes from `benchmark.py`, which drives `agent.run()` directly and never touches this CLI. Anything you see in a chat session is a single un-repeated sample.

More in [`samples/`](samples/README.md).

## Part 1 — the tool-definition tax

The cleanest number in the folder comes from a prompt that calls **no tool at all**: *"Reply with exactly the word READY."* One round-trip. Everything fixed except how many tool schemas were serialized into the request.

| servers connected | tools | input tokens | vs. 1 server | tokens per extra tool |
|---|---:|---:|---:|---:|
| Northwind | 5 | 1,507 ± 0 | 1.00x | — |
| + Helios | 15 | 3,378 ± 0 | 2.24x | 187 |
| + Meridian | 35 | 7,235 ± 0 | 4.80x | 191 |
| + Lumen | 75 | 14,224 ± 0 | 9.44x | 182 |
| + Bastion | 155 | **27,086 ± 0** | **17.97x** | 171 |

**170–191 input tokens per tool per request** — call it ~180 — near-flat across a 31x range in tool count. That matches the MCP-vs-CLI folder's independently-measured ~178 tokens per tool per request on a single server — a different catalogue, a different domain, the same slope. The number travels.

Zero standard deviation across all three runs, at every step: the tool block is deterministic text. It is not an average you might get lucky on. It is a fixed bill.

The same thing measured without a model in the loop:

```
$ python show_schema.py --servers 5 --weigh
  Northwind Docs       5 tools     2,774 chars
  Helios Helpdesk     10 tools     5,014 chars
  Meridian CRM        20 tools    10,149 chars
  Lumen Analytics     40 tools    18,264 chars
  Bastion Infra       80 tools    33,377 chars
  TOTAL              155 tools    69,578 chars
```

**Sixty-nine thousand characters**, re-serialized into every request for the life of the conversation. That is what "we hooked up the infra server too, it's free" actually costs.

### What it extrapolates to

At Sonnet's list price of $3.00 per million input tokens:

- **One turn**, full stack attached, before the agent does any work: **27,086 input tokens ≈ $0.081**.
- **A 40-turn working session**: **1,083,440 input tokens ≈ $3.25** — of which **1,023,160 tokens ($3.07)** are tool definitions for servers the agent may never touch.
- **The same session with only the server it needs**: **60,280 tokens ≈ $0.18**.

That is an 18x difference in input spend for identical work. It is a straight-line extrapolation of a measured per-turn cost, not a measured 40-turn conversation, and it assumes no prompt caching — see the caveats.

Real tasks cost more than the probe because they take two round-trips and the tool block is re-sent on each:

| servers | tools | input tok / run | output tok | round-trips | wall |
|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 3,375 | 182 | 2.1 | 6.1s |
| 2 | 15 | 7,198 | 186 | 2.1 | 6.0s |
| 3 | 35 | 15,169 | 181 | 2.1 | 6.1s |
| 4 | 75 | 29,938 | 185 | 2.1 | 6.5s |
| 5 | 155 | **56,815** | 189 | 2.1 | 7.5s |

**16.8x more input tokens for identical work.** Note the output column: 182 tokens at 5 tools, 189 at 155. The model is not deliberating harder or hedging with 155 options — all of the growth is on the input side, and all of it is definitions.

## Part 2 — confusion: the part the MCP-vs-CLI folder could not measure

That folder found 35/35 correct selections, but only because it had three conventionally-named commands and nothing to confuse them with. Here wrong selection is genuinely available: 20 planted near-duplicates plus 130 more tools on top, and 15 tasks with exactly one correct answer each.

| servers | tools | qualified | implied | adversarial | overall |
|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |
| 2 | 15 | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |
| 3 | 35 | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |
| 4 | 75 | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |
| 5 | **155** | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |
| 5 | 155 *(position control — Northwind registered **last**)* | 15/15 | 15/15 | 15/15 | **45/45 · 100%** |

**270/270 correct first selections. Zero wrong-server calls. Zero recoveries needed.**

And not only the first call. Across all **292 tool calls** in the entire sweep:

> **Zero calls to any of the 150 non-Northwind tools. Ever.** Not a mis-selection, not an exploratory call, not a recovery. Those 150 tools sat in the context window costing 25,579 input tokens a turn and were never once touched.

The only multi-call runs were 22 instances of `search_docs → get_doc` — find the page, then read it. That is correct chaining on a search task, not recovery from a bad pick. Round-trips stayed flat at 2.1 across every step.

### What we tried, so nobody thinks we did not try

A 100% result is only worth something if the test could plausibly have failed. Four escalations, in order:

1. **Plant near-duplicates across vendors.** Five names for "find a document", five for "read one", five for "list containers" — 20 planted collisions. No effect.
2. **Stop naming the vendor.** The `implied` tier never says "Northwind"; it leans on the `NW-####` id convention or Northwind's own self-description, so the model has to read descriptions rather than pattern-match a proper noun. No effect — 75/75.
3. **Make a rival tool the better keyword match.** The `adversarial` tier. *"I need the failover runbook for the database"* sits next to Bastion's `failover_database`, which would execute a production failover. *"What documentation spaces do we have"* sits next to `list_doc_spaces`, a near-identical name on another server. No effect — 75/75.
4. **Bury the right answers at the bottom of the list.** Position in a flat tool list is a known selection bias, and Northwind was registered first. `--reverse` puts the five correct tools *after* the other 150. No effect — 45/45.

What would be needed to break it is genuine ambiguity, not more tools: two descriptions both honestly applicable to the request — at which point there is no correct answer to score against, and it is a spec problem rather than a selection problem. Or exact name collisions across servers, which the adapter resolves before the model sees them. Or a smaller model.

It held up for an unglamorous reason worth saying out loud: **every Northwind description names Northwind.** Description quality *is* selection accuracy, and these descriptions were written carefully — which is the advice, and also exactly why the experiment did not break. A server shipping terse, vendor-anonymous descriptions is running a different experiment.

Full tables, including the bait each adversarial task carried, in [`results/accuracy.md`](results/accuracy.md).

### What the scored suite could not show: ambiguity produces fan-out

The scored tasks all have exactly one correct answer — that is what makes them scoreable, and it is also their limit. A request with *no* correct answer behaves differently, and the interactive agent is where you can see it.

The identical question, `"find me the docs on rate limits"` — a topic that exists in none of the fixtures:

| | tool calls | what it did |
|---|---:|---|
| `--servers 1` (5 tools) | 4 | `search_docs` → `search_docs` (reworded) → `list_spaces` → `search_docs` (scoped to a space). All Northwind. |
| `--servers 5` (155 tools) | 3 | `search_documentation` (**Bastion**) → `search_docs` (**Northwind**) → `find_documents` (**Helios**). Three vendors. |

Both fan out when there is nothing to find. What changes at 155 tools is the *direction*: with five servers connected the agent queries three different companies' systems for an internal engineering topic, because three of them plausibly could have it.

**This is one interactive run each, not a measurement** — no repeats, no scoring, and an under-specified request has no right answer to score against. It is reported because it is the honest complement to the 270/270: well-specified requests do not degrade, and under-specified ones spread across vendors instead of failing outright. If you want to make the point in the room, this is the command to type.

## The conclusion

**Adding a server is not free, and it is not a one-time cost.** Every tool description is text in the model's context on every turn. Five reasonable vendors produce a 27,086-token entry fee that the agent pays before it does anything, on every turn, forever.

**But the failure mode is the bill, not the behaviour.** We tried four ways to make the agent pick the wrong tool at 155 options and could not. That is a sharper argument than the one we went looking for: nobody has to be talked out of a reliability scare, they have to be shown an invoice.

The practical guidance:

- **Connect the servers a given agent actually needs, not every server your company runs.** One agent per job, each with its own small set. A docs agent does not need the infra server.
- **Ship the tools agents call.** A server with 80 tools imposes 80 tools' worth of tax on every consumer, forever.
- **Price the connection before you make it.** ~180 input tokens per tool per turn is the exchange rate.
- **Do not economize on descriptions.** They are what selection accuracy is made of. Cut *tools*, not words.

**Prompt caching is the real mitigation, and we did not measure it.** Anthropic's prompt caching can amortize a large static tool block across the turns of a session, cutting the repeat cost of cache hits substantially. It would soften this tax considerably — not eliminate it: the first request pays in full, cache entries expire, and changing the tool set invalidates the block. It is the obvious follow-up experiment.

The direction past that, named here but not built: load tool definitions **on demand** — as importable modules read from a filesystem rather than injected into every request — so the schema tax scales with what an agent uses instead of what it has installed. Anthropic has published this as "code execution with MCP". It is the same conclusion the MCP-vs-CLI folder reached from the other direction.

## Caveats, stated plainly

- **One model, one task family.** `claude-sonnet-5` only. A smaller model would plausibly be more susceptible to near-duplicate confusion, and this folder does not test that.
- **No prompt caching, and this is the big one.** Anthropic's prompt caching can amortize a large static tool block across turns in a session, cutting the repeat cost of cache hits substantially. That would soften the per-turn tax considerably without eliminating it: the first request still pays in full, cache entries expire, and a changed tool set invalidates the block. **We did not measure it.** If someone in the room raises it, the honest answer is "yes, that is the right mitigation, and it is the obvious follow-up experiment."
- **Tool names are unique across the five servers.** Real vendors collide outright — two servers both shipping `search_docs` is entirely plausible. `langchain-mcp-adapters` flattens every server into one namespace, so a genuine duplicate would silently shadow, and we would have measured adapter behaviour rather than model behaviour. `catalog.py` asserts uniqueness at import. **The collision problem is real; it just is not what this folder measures.**
- **Payloads are small.** The fixture responses are a few hundred bytes. Nothing here says how tool-result volume interacts with tool-definition volume.
- **Transport is not a variable.** The committed numbers were measured over stdio; the servers now run over HTTP. The tool block serialized into the Anthropic request is byte-identical either way (69,578 chars both times), and all five tax-probe points reproduce to the digit over HTTP — 1,507 / 3,378 / 7,235 / 14,224 / 27,086. The results were therefore **not** re-run.
- **Wall clock is API latency.** Reported for completeness, not for conclusions.
- **The distractor tools were never called at all.** They return honest empty results if they ever are. That is the point: they cost their full schema regardless.

## Files

| File | What it is |
|---|---|
| `catalog.py` | The five vendor catalogues — 155 tool definitions, with the 20 planted near-duplicates marked. Self-checks name uniqueness and counts at import. |
| `servers/server.py` | One generic FastMCP server, instantiated five times. Serves HTTP on its assigned port (`--stdio` escapes to spawned-subprocess mode). Real signatures, so FastMCP derives real JSON schemas. |
| `start_servers.sh` / `stop_servers.sh` | Start and stop all five on ports 8010–8014, logging to `servers/logs/`. |
| `agent.py` | The agent. Connects to the running servers by URL; never spawns them. **No arguments opens a chat loop** (`shared/repl.py`) — demonstration only. `--servers N` connects the first N vendors; `--ask` asks one free-form question; `--task` runs one scored task; `--reverse` is the tool-position control; `--probe` is the no-tool tax probe. |
| `tasks.py` | The 15 tasks — qualified, implied and adversarial — each with exactly one correct tool. |
| `metrics.py` | Token, round-trip and selection accounting from `usage_metadata`. Measured, never estimated. |
| `benchmark.py` | The harness: probes, matrix, position control; writes `results/`. |
| `show_schema.py` | What the model actually receives for a tool, and what the whole block weighs. No API key. |
| `results/results.json` | Every run, every metric, every tool call. |
| `results/chart.txt` | Rendered ASCII chart. |
| `results/accuracy.md` | Selection accuracy tables, including every wrong pick. |
| `results/report.md` | The written report, generated from the JSON. |
| `results/traces.txt` | Tool-call trace for the first run of every cell. |
| `index.html` | Self-contained session page. No external requests. |
