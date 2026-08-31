# 06 — MCP Breakdown

Take apart three real MCP servers — Zapier, Snowflake and Datadog — using only
what each vendor publishes.

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

Everything at once, saved to a file you can diff later:

```bash
./06-mcp-breakdown/inspect.sh all > run-$(date +%F).txt 2>&1
```

`probe` returns `401` from Zapier and Datadog; Snowflake has no shared host.
Expected output for every command is in `samples/README.md`.

## Your task

You are evaluating three production MCP servers — Zapier, Snowflake and Datadog
— the way you would before connecting one to your own agents. `WORKSHEET.md` is
the set of questions; you fill in one copy per server and keep it.

The first thing you will find is that none of the three will list their tools
without a credential. That is the realistic case, so the exercise is to work out
what you *can* establish from what each vendor publishes.

- **Run `inspect.sh probe` and `inspect.sh oauth`.** Note what each server
  returns without a credential, and what its public OAuth metadata tells you.
- **Run `inspect.sh zapier`**, then fill in a copy of `WORKSHEET.md` for it.
  Pay attention to how many tools it actually exposes versus how many actions
  sit behind them.
- **Run `inspect.sh snowflake`** and fill in a second copy. This is the only one
  of the three with readable source, and the only one with real cost controls.
- **Run `inspect.sh datadog`** and `inspect.sh tokens`, then fill in a third.
  Datadog documents its own context cost and lets you filter which toolsets
  load — compare the numbers it publishes with what you measured in `07`.
- **Put the three side by side.** For each: what would you change before
  adopting it, and how would you notice if it changed under you after you had?

Write the tool counts and commit hashes your run prints onto the worksheet. The
vendors change these weekly, so an undated answer is worthless.

## Troubleshooting

**`missing: jq — brew install jq`** — install `jq`.

**Anything other than two 401s from `probe`** — a proxy, a captive portal, or
no network.

**Counts that do not match `samples/`** — the vendor moved. Write down what you
got.
