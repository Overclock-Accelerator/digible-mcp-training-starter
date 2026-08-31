# Sample runs — 09-alt

Every output below was recorded from this folder as committed. If yours differs,
your environment is wrong, not the demo.

No server is involved here: each agent reads `digible.db` directly, in its own
way. That is the point of the folder.

---

## 0. The measurement — no API key needed

```bash
cd 09-alt-mcp-query-sprawl
python count_duplication.py
```

```
DATA ACCESS PER FILE
  Blank lines, comments and docstrings excluded throughout.
  ------------------------------------------------------------------------
  file                                 lines   data access    tools   share
  channel efficiency (helper)             88            49        0     56%
  call recovery                          173            70       94     40%
  channel efficiency                      87            24       62     28%
  leasing attribution                    175            71       84     41%
  property funnel                        141            56       70     40%
  spend pacing                           153            67      110     44%
  tour trends                            155            43       85     28%
  ------------------------------------------------------------------------
  TOTAL                                  972           380      505     39%

SHARED PRIMITIVES, SOLVED SEPARATELY
  Independent implementations of the same small problem.
  ------------------------------------------------------------------------
  primitive                   files  impls   solved separately in
  open the database               5      6   ...
  resolve a period                6     10   ...
  look up a property              7      9   ...
  fetch spend                     4      7   ...
  fetch leads                     4      5   ...
  format numbers                  3      7   ...
```

`--detail` names every function.

---

## 1. Spend pacing

```bash
cd agents
python agent_spend_pacing.py "which properties are pacing over budget in May?"
```

```
──── tools invoked ───────────────────────────────────────────────
  1. pacing(month="May")
     → 1,3xx chars · "Budget pacing — 2026-…"
──────────────────────────────────────────────────────────────────
```

The tool's own output:

```
Budget pacing — 2026-05
  media pace = media spend / media budget; invoiced = media + Digible fees
  property                         budget      media    pace    invoiced  of budget  status
  Bishop Arts Flats                $2,630     $1,908   72.5%      $3,748     142.5%  under
  Camelback Vista                  $1,985     $1,289   65.0%      $2,324     117.1%  under
  Cherry Creek Commons             $4,853     $3,790   78.1%      $5,846     120.4%  under
  Legacy Trails                    $5,509     $4,190   76.1%      $6,798     123.4%  under
  ...
```

Nothing is over on media. Everything is over once fees are on the invoice. Both
numbers are true and the agent is told to report both.

---

## 2. Tour trends

```bash
python agent_tour_trends.py "which properties saw tour bookings drop in June compared with May?"
```

```
──── tools invoked ───────────────────────────────────────────────
  1. tour_volume(month="June", compare_to_prior=true)
     → 799 chars · "Tours scheduled — 202…"
──────────────────────────────────────────────────────────────────
Five properties had meaningful (≥10%) tour drops from May to June 2026:

1. Camelback Vista   — 66 → 46  (-30.3%)
2. Legacy Trails     — 131 → 107 (-18.3%)
3. Sundance Ridge    — 45 → 38  (-15.6%)
4. The Alder at Lowry— 45 → 39  (-13.3%)
5. Peachtree Row     — 92 → 80  (-13.0%)
```

**Write these five properties and five percentages down.** After you have
rewritten the agents against one server, ask the same question again and check
that every one of them still matches. That is the test of the refactor: it moved
the code, not the answers.

---

## 3. Property funnel

```bash
python agent_property_funnel.py "show me the funnel for Legacy Trails in May"
```

```
──── tools invoked ───────────────────────────────────────────────
  1. funnel(property_name="Legacy Trails", period="2026-05")
     → 343 chars · "Funnel — Legacy Trail…"
──────────────────────────────────────────────────────────────────
Legacy Trails, May 2026: 20 new leases signed from 410 leads (4.9%).

The worst leak is tours scheduled → completed: only 83 of 131 scheduled
tours actually happened (63.4% show rate).
```

---

## 4. Call recovery

```bash
python agent_call_recovery.py "which properties are missing the most calls in June?"
```

```
──── tools invoked ───────────────────────────────────────────────
  1. missed_calls(month="2026-06")
     → 1,151 chars · "Calls — 2026-06\n  pro…"
──────────────────────────────────────────────────────────────────
Vireo Uptown is the worst offender in June — 454 missed calls out of 762
total (a 59.6% miss rate).

Bishop Arts Flats has the worst rate — 83.8% of its calls go unanswered
(196 of 234).
```

---

## 5. The conversation, which is the default

Run any agent with no arguments:

```bash
python agent_channel_efficiency.py
```

```
Digible — Channel Efficiency
──────────────────────────────────────────────
  cost per lead by channel in May
  same thing but just for Harborview 900
  which channel has the best CTR?
  exit / quit / Ctrl-D to leave

you › cost per lead by channel in May
```

Ask the follow-up — "same thing but just for Harborview 900" — and watch the
trace: the agent carries the month across turns and only the property changes.
Ask a third question the tools cannot answer and the trace prints
`(none — the model answered without calling a tool)`. Knowing when *not* to call
a tool is worth pointing at.

---

## 6. The thing to do next

Open the six agent files side by side and find every function that turns a month
into a pair of dates. There are ten of them, in six files, and they are all
correct. Then design the tool set that replaces all ten with one, and build it.
