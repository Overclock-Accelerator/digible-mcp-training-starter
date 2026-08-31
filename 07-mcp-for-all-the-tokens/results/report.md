# What five MCP servers cost one agent

Measured 2026-08-31T13:17:01+00:00 with `anthropic:claude-sonnet-5`, 3 runs per cell. Token counts come from the Anthropic API's own `usage_metadata`, summed across every round-trip. Nothing here is estimated.

## The stack

| # | vendor | domain | tools | cumulative |
|---:|---|---|---:|---:|
| 1 | Northwind Docs | internal engineering documentation | 5 | 5 |
| 2 | Helios Helpdesk | customer support desk | 10 | 15 |
| 3 | Meridian CRM | sales and customer records | 20 | 35 |
| 4 | Lumen Analytics | product analytics and BI | 40 | 75 |
| 5 | Bastion Infra | cloud infrastructure platform | 80 | 155 |

## 1. The tool-definition tax

A prompt that calls no tool at all — one round-trip, everything fixed
except how many schemas were serialized into the request.

| servers connected | tools | input tokens | vs. 1 server | tok/tool |
|---|---:|---:|---:|---:|
| Northwind Docs | 5 | 1507 ± 0 | 1.00x | — |
| Northwind Docs, Helios Helpdesk | 15 | 3378 ± 0 | 2.24x | 187.1 |
| Northwind Docs, Helios Helpdesk, Meridian CRM | 35 | 7235 ± 0 | 4.80x | 190.9 |
| Northwind Docs, Helios Helpdesk, Meridian CRM, Lumen Analytics | 75 | 14224 ± 0 | 9.44x | 181.7 |
| Northwind Docs, Helios Helpdesk, Meridian CRM, Lumen Analytics, Bastion Infra | 155 | 27086 ± 0 | 17.97x | 170.5 |

**170–191 input tokens per tool per request** (last step: 170), near-flat across a 31x range in tool count. Connecting all five vendors costs **25,579 input tokens on every single turn**, before the agent does any work at all.

Standard deviation is zero at every step: the tool block is deterministic text, not an average you might get lucky on.

### What that extrapolates to

At list price ($3.00 per million input tokens):

- One turn with the full stack attached: **27,086 input tokens**, about **$0.081**.
- A 40-turn working session: **1,083,440 input tokens**, about **$3.25** — and **1,023,160** of those tokens are tool definitions for servers the agent may never touch.
- Connecting only the one server actually needed: **60,280 tokens**, about **$0.18**.

That is a straight-line extrapolation of a measured per-turn cost, not a measured conversation. It also assumes no prompt caching; see the caveats.

## 2. Selection accuracy

| servers | tools | correct | accuracy | wrong-server | extra round-trips |
|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 45/45 | 100.0% | 0 | 4 |
| 2 | 15 | 45/45 | 100.0% | 0 | 3 |
| 3 | 35 | 45/45 | 100.0% | 0 | 3 |
| 4 | 75 | 45/45 | 100.0% | 0 | 4 |
| 5 | 155 | 45/45 | 100.0% | 0 | 4 |
| 5 *(control: Northwind last)* | 155 | 45/45 | 100.0% | 0 | 4 |

Wrong first selections across the whole sweep: **0**.
Tool calls made in total: **292**, of which calls to any of the 150 non-Northwind tools: **0**.

Full breakdown, including the bait each adversarial task carried, in `accuracy.md`.

