# 09 — Query Sprawl

**Six agents, six questions, one database — and six private re-implementations
of the same handful of data primitives. The tool set they all needed was
smaller than any one of them.**

That is the ONE idea. This folder is a simpler alternative to
`09-mcp-architecture`: same database, no business-semantics adjudication. Every
number in here is correct. Nothing disagrees with anything. The only problem is
that the same small problems were solved six times.

---

## The six agents

Six questions an account manager at a multifamily marketing agency actually
asks in a week. They were built by six different people, in the order the
requests came in.

| agent | the question | data it needs |
|---|---|---|
| `agent_spend_pacing.py` | Which properties are pacing over budget this month? | spend, campaigns, properties, month |
| `agent_channel_efficiency.py` | What does a lead cost us on each channel? | spend, leads, properties, month |
| `agent_tour_trends.py` | Which properties saw tour bookings drop? | tours, leads, properties, month |
| `agent_property_funnel.py` | What does the funnel look like at one property? | leads, tours, applications, leases, properties, dates |
| `agent_leasing_attribution.py` | Which channels drive the most leases? | leases, leads, spend, properties, period |
| `agent_call_recovery.py` | Where are we losing phone calls? | calls, spend, properties, month |

Read the table by column, not by row. **Four of them need spend. Four need
leads. Two need tours. Two need leases. All six need to turn "May" into a pair
of dates and "Legacy Trails" into a property.** None of them share a line of
code to do it.

---

## Six shapes of the same thing

The duplication here is mechanical, not semantic. Each agent's data access is
written in a different style, because six people write code six ways:

| agent | style |
|---|---|
| spend pacing | raw SQL inline in the tool functions, one module-level connection |
| channel efficiency | a small private helper module, `_spendlib.py` |
| tour trends | pulls the tables into memory, filters in Python |
| property funnel | a fresh connection per call, walks up the tree to find the file |
| leasing attribution | its own period grammar — months, quarters, halves, ranges |
| call recovery | its own presentation layer — a table renderer and money formatter |

**None of these is a strawman.** Every one is something a competent person
ships under deadline. The helper module is genuinely tidy. The table renderer
is genuinely nicer than string concatenation. Reading them should feel like
reading your own repository, which is the point.

---

## Setup

From the repo root, if you haven't already:

```bash
./setup.sh                                  # creates .venv, installs requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env.local
source .venv/bin/activate
```

`digible.db` is committed — a byte-for-byte copy of the one in
`09-mcp-architecture`, which `09-mcp-architecture/build_db.py` regenerates
deterministically. 14 properties, 5 management companies, January through June
2026, about 110,000 rows. All data is synthetic; the vocabulary and the fee
structures are real.

---

## Run it

Each agent takes no arguments and opens a conversation:

```bash
cd 09-mcp-architecture/agents

python agent_spend_pacing.py
python agent_channel_efficiency.py
python agent_tour_trends.py
python agent_property_funnel.py
python agent_leasing_attribution.py
python agent_call_recovery.py
```

Pass a question to answer once and exit — for samples and tests:

```bash
python agent_spend_pacing.py "which properties are pacing over budget in May?"
```

Every agent prints its tool calls before its answer. Watch the trace: six
agents, six different tool names, all of them reading the same four tables.

---

## Then count it

```bash
python count_duplication.py            # no API key needed
python count_duplication.py --detail   # name every implementation
```

It reads the files with `ast`, classifies every line as data access or not, and
counts how many times each shared primitive was solved independently. The
fenced `# --- plumbing ---` block every agent carries — shared/ onto the path,
the key out of `.env.local`, argparse — is identical in all six and counted in
neither column. As committed:

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

Forty per cent of this folder is plumbing, written six times.

---

## The exercise

**Design the tool set.**

1. Read the six agents. For each one, write down what it actually asks the
   database for — not the SQL, the *question*: "spend, for these properties,
   over this window, grouped this way."
2. Find the primitives underneath. There are fewer than you think.
3. Design a **tight** set of MCP tools that serves all six.
4. Build one server. Rewrite the agents against it.

**The discipline is in step 3, and it is the whole exercise.** The easy move is
one tool per question: `pacing_report`, `cost_per_lead`, `tour_drop_report`,
`property_funnel`, `leases_by_channel`, `missed_calls`. That gets you six tools,
each of which serves exactly one agent, and the seventh question next month
needs a seventh tool. You will have moved the sprawl behind a server, not
removed it.

The move that works is to find the two or three *shapes* that every question is
made of, and expose those with enough parameters to compose. Then the seventh
question needs no new tools at all.

Two constraints to design against:

- **Tool definitions cost tokens on every single turn.** `07-mcp-for-all-the-tokens`
  measures it: roughly 170–190 input tokens per tool per request, whether or not
  the model calls it. Twelve tools is a permanent tax on every conversation the
  agent ever has.
- **A model choosing between 12 similar tools chooses worse than one choosing
  between 6 distinct ones.** Overlapping tools are not free even when they are
  cheap.

Aim for **five or six tools**. If you land at a dozen, you have written one tool
per question and missed the point.

When you have your answer, open `10-mcp-architecture-solved/`.

---

## What this folder does NOT teach

There are no bugs planted here, and no two agents disagree. If you want the
exercise where six teams computed genuinely different numbers from the same
tables and all of them defended their answer, that is `09-mcp-architecture` —
a harder and more argumentative version of the same lesson.

This one is about redundancy alone: what it costs to solve one problem six
times, even when you solve it correctly six times.
