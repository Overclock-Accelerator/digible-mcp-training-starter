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

The `agents/` directory contains six agents. Each answers a different question
about the same database, and each implements its own data access. Consolidate
the shared capability into a single MCP server and rewrite the agents against
it.

Begin by running `python count_duplication.py`, which requires no API key. It
reports the proportion of each agent that is data access, and the number of
independent implementations of each underlying primitive.

1. **Survey the agents.** For each of the six, record the question it answers,
   expressed in English rather than SQL. Note the data-access style each one
   uses: inline SQL, a private helper module, retrieve-then-filter in Python,
   per-call connection handling, its own period parsing, its own formatting.

2. **Identify the shared primitives.** Opening the database, resolving a period,
   looking up a property, fetching spend, fetching leads, fetching calls. Record
   how many of the six implement each one separately.

3. **Design the tool set.** Target five or six tools. A tool per question
   reproduces the existing duplication in a new location. Identify the query
   shapes that compose — spend, funnel, calls, and the lookups they require —
   and express variation through a `group_by` parameter rather than through
   additional tools.

4. **Implement the server.** One process, HTTP transport, started independently
   of any agent.

5. **Rewrite the six agents against the server.** All data access should be
   absent from the agent files when you are finished.

Tool definitions consume approximately 170–190 input tokens each per request,
whether or not the tool is called. The five-or-six target follows from that
cost.

## Bonus

### 1. Deploy the server to Horizon

Create a separate GitHub repository containing `server.py` at the root, a
`requirements.txt` pinning `fastmcp==3.4.7`, and a `.python-version` file
containing `3.12`. Commit `digible.db` and open it read-only from a path
resolved relative to the source file rather than the working directory; the
runtime filesystem is ephemeral and no process may write to it.

Connect the repository in Horizon, set the entrypoint to `server.py:mcp`, and
deploy. `04-mcp-deployment` documents the full sequence.

### 2. Connect Claude Desktop to your server

Add the deployed URL as a connector and query it in plain English, without code
or a terminal. `05-mcps-for-all` documents the setup.

Then ask someone unfamiliar with your implementation to use it. Tool names and
descriptions constitute the entire interface available to that user, and any
required parameter is a value they must know to supply.

## Troubleshooting

**`ModuleNotFoundError`** — the virtualenv is not active. Run
`source .venv/bin/activate` from the repo root.

**`error: ANTHROPIC_API_KEY is not set`** — put your key in `.env.local` at the
repo root. `count_duplication.py` does not need one.
