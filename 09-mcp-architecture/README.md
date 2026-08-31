# 09 — MCP Architecture

Six agents answering six questions against one database, each with its own
private data-access code.

## Run

All commands are from the repo root, with the virtualenv active. There is no
server — each agent reads `digible.db` directly.

```bash
cd 09-mcp-architecture/agents
python agent_spend_pacing.py
python agent_channel_efficiency.py
python agent_tour_trends.py
python agent_property_funnel.py
python agent_leasing_attribution.py
python agent_call_recovery.py
```

No arguments opens a chat; a question answers once and exits. Counting the
duplication needs no API key:

```bash
python 09-mcp-architecture/count_duplication.py
python 09-mcp-architecture/count_duplication.py --detail   # names every implementation
```

## Prompts

```
which properties are pacing over budget in May?
which properties saw tour bookings drop in June compared with May?
show me the funnel for Legacy Trails in May
which properties are missing the most calls in June?
cost per lead by channel in May
same thing but just for Harborview 900
```

Tour trends returns Camelback Vista 66→46, Legacy Trails 131→107, Sundance
Ridge 45→38, The Alder at Lowry 45→39, Peachtree Row 92→80.

## Results

`count_duplication.py`, as committed:

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

## Your task

Six agents answer six different questions about the same database, and every one
of them wrote its own way to get the data. Your job is to find what they share
and put it behind a single MCP server.

Start with `python count_duplication.py`. It needs no API key and reports how
many lines of each agent are data access, plus how many times each underlying
primitive was independently implemented.

- **Read the six agents** and write down what each one asks the database for —
  the question in English, not the SQL. They are in `agents/`, one file each,
  and each uses a deliberately different style: inline SQL, a private helper
  module, pull-everything-and-filter, its own connection handling, its own
  period parsing, its own formatting.
- **List the primitives underneath.** Opening the database, resolving a period,
  looking up a property, fetching spend, fetching leads, fetching calls. Note
  how many of the six solve each one separately.
- **Design a tool set that serves all six.** Aim for five or six tools. This is
  the real work: a tool per question is not a design, it is the same sprawl on
  a different machine. Look for the shapes that compose — a spend query, a
  funnel query, a calls query, and whatever lookups they need — with the variety
  living in a `group_by` parameter rather than in more tools.
- **Build one server** exposing them, running as its own process over HTTP.
- **Rewrite the agents against it.** They should get much thinner; the data
  access should disappear from them entirely.
- **Re-run `count_duplication.py`** and compare.

Tool definitions cost roughly 170–190 input tokens each per request whether or
not they are called, so every extra tool is a permanent tax on every turn. That
is the constraint that makes "five or six" a real target rather than a
preference.

## Bonus

### 1. Deploy the server to Horizon

Push it to its own GitHub repo with `server.py` at the root, a
`requirements.txt` pinning `fastmcp==3.4.7`, and a `.python-version` containing
`3.12`. Commit `digible.db` and open it read-only from a path relative to the
file, not the working directory — the runtime filesystem is ephemeral and
nothing may write to it.

Connect the repo in Horizon, set the entrypoint to `server.py:mcp`, and deploy.
`04-mcp-deployment` has the full sequence.

### 2. Connect Claude Desktop to your new MCP

Add the deployed URL as a connector, then ask it questions in plain English —
no code, no terminal. `05-mcps-for-all` covers the setup.

Then hand it to someone who has not seen your code and watch what happens. A
tool set that works for your six agents is not automatically usable by a
person: the names and descriptions are the only interface they get, and every
required parameter is something they now have to know to supply.

## Troubleshooting

**`ModuleNotFoundError`** — run `source .venv/bin/activate` from the repo root.

**`error: ANTHROPIC_API_KEY is not set`** — put your key in `.env.local` at the
repo root. `count_duplication.py` does not need one.
