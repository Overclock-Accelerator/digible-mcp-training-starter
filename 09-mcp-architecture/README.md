# 09 — MCP Architecture

Six agents answering six questions against one database, each with its own
private data-access code. The activity is to design the MCP tool set that
replaces all six.

## Files

| | |
|---|---|
| `agents/agent_spend_pacing.py` | Which properties are pacing over budget this month? |
| `agents/agent_channel_efficiency.py` | What does a lead cost us on each channel? |
| `agents/agent_tour_trends.py` | Which properties saw tour bookings drop? |
| `agents/agent_property_funnel.py` | What does the funnel look like at one property? |
| `agents/agent_leasing_attribution.py` | Which channels drive the most leases? |
| `agents/agent_call_recovery.py` | Where are we losing phone calls? |
| `agents/_spendlib.py` | A private helper module, used by one agent |
| `count_duplication.py` | Counts the duplication; no API key needed |
| `digible.db` | 14 properties, 5 management companies, 12 channels, Jan–Jun 2026 |
| `samples/RUNS.md` | Captured runs |

## Run it

All commands are from the repo root, with the virtualenv active. No server is
involved — each agent reads `digible.db` directly.

```bash
python 09-mcp-architecture/agents/agent_spend_pacing.py
python 09-mcp-architecture/agents/agent_channel_efficiency.py
python 09-mcp-architecture/agents/agent_tour_trends.py
python 09-mcp-architecture/agents/agent_property_funnel.py
python 09-mcp-architecture/agents/agent_leasing_attribution.py
python 09-mcp-architecture/agents/agent_call_recovery.py
```

No arguments opens a chat; a question answers once and exits:

```bash
python 09-mcp-architecture/agents/agent_spend_pacing.py "which properties are pacing over budget in May?"
```

Count the duplication — no API key needed:

```bash
python 09-mcp-architecture/count_duplication.py
python 09-mcp-architecture/count_duplication.py --detail
```

```
  375 of 973 lines across the six agents and their one helper module (39%)
  are data access.
  174 further lines are the identical per-file plumbing block, counted nowhere.

  open the database        5 files   6 implementations
  resolve a period         6 files  10 implementations
  look up a property       7 files   9 implementations
  fetch spend              4 files   7 implementations
  fetch leads              4 files   5 implementations
  format numbers           3 files   7 implementations
```

## Sample prompts

| agent | type this | you get |
|---|---|---|
| spend pacing | `which properties are pacing over budget in May?` | nothing over on media; everything over once fees are on the invoice |
| tour trends | `which properties saw tour bookings drop in June compared with May?` | five properties: Camelback Vista 66→46, Legacy Trails 131→107, Sundance Ridge 45→38, The Alder at Lowry 45→39, Peachtree Row 92→80 |
| property funnel | `show me the funnel for Legacy Trails in May` | 410 leads → 20 leases (4.9%); 83 of 131 scheduled tours completed |
| call recovery | `which properties are missing the most calls in June?` | Vireo Uptown, 454 of 762 (59.6%); Bishop Arts Flats worst rate at 83.8% |
| channel efficiency | `cost per lead by channel in May`, then `same thing but just for Harborview 900` | the follow-up keeps the month and changes only the property |

## The task

Design the tool set.

1. Read the six agents. For each, write down what it asks the database for — not
   the SQL, the question: "spend, for these properties, over this window,
   grouped this way."
2. Find the primitives underneath.
3. Design a set of MCP tools that serves all six. Aim for five or six.
4. Build one server. Rewrite the agents against it.

Two constraints: tool definitions cost roughly 170–190 input tokens per tool per
request, whether or not the model calls them (`07-mcp-for-all-the-tokens`); and
a model choosing between 12 similar tools chooses worse than one choosing
between 6 distinct ones.


## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**`error: ANTHROPIC_API_KEY is not set`** — put your key in `.env.local` at the
repo root. `count_duplication.py` does not need one.
