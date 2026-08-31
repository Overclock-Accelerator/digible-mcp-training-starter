# Capabilities in context vs. capabilities on disk

Model `anthropic:claude-sonnet-5`, 5 runs per row, generated 2026-08-31T12:41:03+00:00.

Both arms are padded from the *same* 37-entry catalogue (`pad_catalog.py`), so
"40 tools" and "40 commands" are the same 40 capabilities. MCP re-sends every
tool's name, description and full JSON schema on every request; the CLI keeps
them on disk and sends one `bash` definition regardless.

Input tokens are summed across every round-trip in a run — the real bill, since
the tool block is re-sent on each one. Output tokens and round-trips are listed
separately because that is where a big CLI catalogue would show its own cost.

## Task: `solve` (briefed)

> Solve the Spelling Bee with letters VALIDTY and center letter V. Report the word count, the total points, and the pangrams.

| interface | capabilities | input tok | vs. 3 | tok per extra cap. | output tok | round-trips |
|---|---:|---:|---:|---:|---:|---:|
| MCP | 3 | 3344 ± 12 | 1.00x | — | 167 ± 7 | 2.0 |
| MCP | 15 | 7629 ± 0 | 2.28x | 357 | 168 ± 1 | 2.0 |
| MCP | 40 | 16320 ± 16 | 4.88x | 351 | 180 ± 16 | 2.0 |
| CLI + bash | 3 | 2220 ± 6 | 1.00x | — | 118 ± 14 | 2.0 |
| CLI + bash | 15 | 2220 ± 6 | 1.00x | 0 | 111 ± 12 | 2.0 |
| CLI + bash | 40 | 2217 ± 0 | 1.00x | -0 | 114 ± 13 | 2.0 |

## Task: `undocumented` (NOT briefed — discovery required)

> Find every dictionary word matching the crossword pattern C_O__W_RD.

| interface | capabilities | input tok | vs. 3 | tok per extra cap. | output tok | round-trips |
|---|---:|---:|---:|---:|---:|---:|
| MCP | 3 | 2548 ± 0 | 1.00x | — | 112 ± 7 | 2.0 |
| MCP | 15 | 6844 ± 13 | 2.69x | 358 | 123 ± 18 | 2.0 |
| MCP | 40 | 15518 ± 0 | 6.09x | 351 | 121 ± 7 | 2.0 |
| CLI + bash | 3 | 2067 ± 1090 | 1.00x | — | 165 ± 122 | 2.6 |
| CLI + bash | 15 | 1392 ± 56 | 0.67x | -56 | 130 ± 56 | 2.0 |
| CLI + bash | 40 | 1572 ± 470 | 0.76x | -13 | 110 ± 23 | 2.2 |
