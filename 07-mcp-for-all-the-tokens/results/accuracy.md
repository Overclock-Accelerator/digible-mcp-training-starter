# Selection accuracy as tool count grows

Model `anthropic:claude-sonnet-5`, 3 runs per task per step, generated 2026-08-31T13:17:01+00:00.

Fifteen tasks, each with exactly one correct tool. Every correct tool lives on
**Northwind Docs**, the server connected at every step — so the right answer
never moves and only the distractor pile grows. Twenty of the other 150 tools
are deliberate near-duplicates of Northwind's five.

`wrong-server` counts runs where the first tool call went to a different
vendor entirely. `recovered` counts wrong first picks that later called the
right tool in the same run.

| servers | tools | phrasing | correct | accuracy | wrong-server | recovered | extra round-trips |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 5 | qualified | 15/15 | 100.0% | 0 | 0 | 0 |
| 1 | 5 | implied | 15/15 | 100.0% | 0 | 0 | 0 |
| 1 | 5 | adversarial | 15/15 | 100.0% | 0 | 0 | 4 |
| 1 | 5 | all | 45/45 | 100.0% | 0 | 0 | 4 |
| 2 | 15 | qualified | 15/15 | 100.0% | 0 | 0 | 0 |
| 2 | 15 | implied | 15/15 | 100.0% | 0 | 0 | 0 |
| 2 | 15 | adversarial | 15/15 | 100.0% | 0 | 0 | 3 |
| 2 | 15 | all | 45/45 | 100.0% | 0 | 0 | 3 |
| 3 | 35 | qualified | 15/15 | 100.0% | 0 | 0 | 0 |
| 3 | 35 | implied | 15/15 | 100.0% | 0 | 0 | 0 |
| 3 | 35 | adversarial | 15/15 | 100.0% | 0 | 0 | 3 |
| 3 | 35 | all | 45/45 | 100.0% | 0 | 0 | 3 |
| 4 | 75 | qualified | 15/15 | 100.0% | 0 | 0 | 0 |
| 4 | 75 | implied | 15/15 | 100.0% | 0 | 0 | 0 |
| 4 | 75 | adversarial | 15/15 | 100.0% | 0 | 0 | 4 |
| 4 | 75 | all | 45/45 | 100.0% | 0 | 0 | 4 |
| 5 | 155 | qualified | 15/15 | 100.0% | 0 | 0 | 0 |
| 5 | 155 | implied | 15/15 | 100.0% | 0 | 0 | 0 |
| 5 | 155 | adversarial | 15/15 | 100.0% | 0 | 0 | 4 |
| 5 | 155 | all | 45/45 | 100.0% | 0 | 0 | 4 |

## Position control — Northwind registered last

Same 155 tools, same tasks, but the server holding every correct answer
is registered *after* the other four instead of before them.

| phrasing | correct | accuracy | wrong-server | extra round-trips |
|---|---:|---:|---:|---:|
| qualified | 15/15 | 100.0% | 0 | 0 |
| implied | 15/15 | 100.0% | 0 | 0 |
| adversarial | 15/15 | 100.0% | 0 | 4 |
| all | 45/45 | 100.0% | 0 | 4 |

## The bait each adversarial task was carrying

| task | prompt | correct tool | nearest wrong match |
|---|---|---|---|
| `a_failover` | I need the failover runbook for the database. Find it for me. | `search_docs` | failover_database (Bastion Infra) — would execute a real failover |
| `a_oncall` | Pull up our on-call expectations page, NW-0091. | `get_doc` | get_oncall_schedule (Bastion Infra) |
| `a_deploy` | Find the blue-green deploy checklist document. | `search_docs` | list_deployments / get_rollout_status (Bastion Infra) |
| `a_whochanged` | Who last changed the failover runbook page NW-4471? | `get_doc_history` | list_audit_events (Bastion Infra) |
| `a_spaces` | What documentation spaces do we have for our internal engineering pages? | `list_spaces` | list_doc_spaces (Bastion Infra) — near-identical name |

## Were the distractor tools touched at all?

Not just "was the first call right" — did any call, anywhere in any run,
reach a tool on a server other than Northwind?

- Task runs: **270**
- Tool calls made: **292**
- Calls to any of the 150 non-Northwind tools: **0**

Multi-call runs, and what the sequence was:

- `search_docs → get_doc` — 22 runs

## Every wrong selection observed

**None.** Across every step, every task and every run, the first tool
call was the correct one. Reported as observed — see the README for
what was tried to induce an error and why it is still a useful result.

