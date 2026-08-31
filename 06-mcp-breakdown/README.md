# 06 — MCP Breakdown

Inspect three real MCP servers — Zapier, Snowflake and Datadog — using only what
each vendor publishes, then fill in a worksheet on each.

## Run

All commands are from the repo root. No API key, no accounts, no Node — you need
`curl`, `jq`, `git` and `python3`.

```bash
./06-mcp-breakdown/inspect.sh deps        # ~1s
./06-mcp-breakdown/inspect.sh probe       # ~5s — run this first
./06-mcp-breakdown/inspect.sh oauth       # ~3s
./06-mcp-breakdown/inspect.sh zapier      # ~15s
./06-mcp-breakdown/inspect.sh snowflake   # ~25s
./06-mcp-breakdown/inspect.sh datadog     # ~30s
./06-mcp-breakdown/inspect.sh tokens      # ~1s
./06-mcp-breakdown/inspect.sh all         # ~90s, everything above
```

`probe` sends an uncredentialed `initialize` to each endpoint:

| | |
|---|---|
| `https://mcp.zapier.com/api/v1/connect` | `401` + `WWW-Authenticate: Bearer …` |
| `https://mcp.datadoghq.com/v1/mcp` | `401 {"errors":["Unauthorized"]}` |
| Snowflake | no shared host exists — the endpoint is per-account |

`tokens` prints the per-request cost of each server's tool surface:

```
  server / configuration                       tools      tokens per request
  ------------------------------------------------------------------------
  Zapier    14 meta-tools, fixed                  14       2,380 - 2,660
  Datadog   default, no query param (core)        23       3,910 - 4,370
  Datadog   ?toolsets=all                        219      37,230 - 41,610
  Datadog   every documented tool                265      45,050 - 50,350
  Snowflake documented cap, one server            50       8,500 - 9,500
```

Save a run to diff against later:

```bash
./06-mcp-breakdown/inspect.sh all > run-$(date +%F).txt 2>&1
```

## Your task

75–90 minutes. Fill in `WORKSHEET.md` — ten questions, one copy per server.

1. `inspect.sh probe` and `inspect.sh oauth` — what you are allowed to know.
2. `inspect.sh zapier` — 20 min, then the Zapier worksheet.
3. `inspect.sh snowflake` — 25 min, then the Snowflake worksheet.
4. `inspect.sh datadog` and `inspect.sh tokens` — 25 min, then the Datadog worksheet.
5. Put the three side by side and answer: what would you change before adopting
   each, and how would you notice if it changed under you?



Both vendors' docs move weekly and Datadog's tool count changes roughly every
other day. Write the counts and commits your run prints on your worksheet.

## Troubleshooting

**`missing: jq — brew install jq`** — install `jq`.

**Anything other than the two 401s from `probe`** — usually a proxy, a captive
portal, or no network.

**`(privilege table not found — the docs page changed)`** — Snowflake reworked
the page. Read it in a browser and note it on your worksheet.

**Counts that do not match this README or `samples/`** — the vendor moved. Write
down what you got.
