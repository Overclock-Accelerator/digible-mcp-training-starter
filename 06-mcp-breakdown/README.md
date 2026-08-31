# 06 — MCP Breakdown

Three production MCP servers — Zapier, Snowflake and Datadog — and what each
one publishes about itself.

## Run

From the repo root. No API key and no accounts; you need `curl`, `jq`, `git`
and `python3`.

```bash
./06-mcp-breakdown/inspect.sh deps        # ~1s
./06-mcp-breakdown/inspect.sh probe       # ~5s, run this first
./06-mcp-breakdown/inspect.sh oauth       # ~3s
./06-mcp-breakdown/inspect.sh zapier      # ~15s
./06-mcp-breakdown/inspect.sh snowflake   # ~25s
./06-mcp-breakdown/inspect.sh datadog     # ~30s
./06-mcp-breakdown/inspect.sh tokens      # ~1s
```

Everything at once, saved to a file:

```bash
./06-mcp-breakdown/inspect.sh all > run-$(date +%F).txt 2>&1
```

`probe` returns `401` from Zapier and Datadog; Snowflake has no shared host.
Expected output for every command is in `samples/README.md`.

## Troubleshooting

**`jq: command not found`** — install `jq`.

**A clone step fails** — rerun the same command; the script skips repos it
already has.
