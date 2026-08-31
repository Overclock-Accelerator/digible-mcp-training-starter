# Samples — copy, paste, compare

Run everything from inside `01-mcp-bee/`, with the repo venv active and
your key in `.env.local` at the repo root.

```bash
source ../.venv/bin/activate
cd 01-mcp-bee
```

If a sample's numbers don't match, your environment is wrong — not the puzzle.

---

## 1. The BEFORE agent — solver as a local tool

```bash
python agent_with_tool.py
```

Expected: a table of every answer, headed by

```
- **Word count:** 34
- **Total points:** 171
- **Pangram:** VALIDITY (15 pts)
```

and on stderr, one line proving the tool actually ran:

```
INFO bee: spelling_bee letters=VALIDTY center=V agent_name=bee-agent
```

The full list starts `VALIDITY 15, ADDITIVITY 10, AVADAVAT 8, LAVALAVA 8,
LIVIDITY 8, VITALITY 8, …` and ends with the ten 4-letter words at 1 point
each (`AVID, DAVY, DIVA, LAVA, TIVY, VAIL, VIAL, VILL, VITA, VIVA`).

---

## 2. The AFTER agent — solver behind MCP

```bash
python agent_with_mcp.py
```

Expected: **the same 34 / 171 / VALIDITY, and the same 34-row table.** That is
the entire point of the folder.

Honest caveat: the numbers, the words and the points are identical because they
come from the same deterministic function. The model's *prose* around the table
is free-form and will vary slightly between runs (`"Results for VALIDTY"` vs
`"Here are the results for the Spelling Bee puzzle with letters VALIDTY"`). Read
the table, not the sentence.

stderr now shows the server being spawned and answering, which is the only
observable difference:

```
INFO  Starting MCP server 'spelling-bee' with transport 'stdio'
INFO  mcp.server.lowlevel.server: Processing request of type ListToolsRequest
INFO  mcp.server.lowlevel.server: Processing request of type CallToolRequest
INFO  bee: spelling_bee letters=VALIDTY center=V agent_name=bee-agent
```

Note the ordering: the client asks *what tools exist* before the model ever runs.
That handshake is what an internal REST API doesn't give you.

---

## 3. A different puzzle (both agents take the same flags)

```bash
python agent_with_tool.py --letters CAPITOL --center C
python agent_with_mcp.py  --letters CAPITOL --center C
```

Expected from both: **136 words, 737 points**, and seven pangrams —
`APOLITICAL, OCCIPITAL, POLITICAL, CAPITOL, COALPIT, OPTICAL, TOPICAL`. The CLI
surface is deliberately the same so the two files stay diffable line for line.

---

## 4. The server on its own, with no agent and no API key

Static introspection — what does this server expose?

```bash
fastmcp inspect mcp_server.py
```

Expected:

```
Server
  Name:         spelling-bee
  Version:      3.4.7
  Generation:   2

Components
  Tools:        1
  Prompts:      0
  Resources:    0
  Templates:    0
```

Interactive — call the tool by hand in the browser and watch the wire:

```bash
fastmcp dev inspector mcp_server.py
```

It is `fastmcp dev inspector`, not `fastmcp dev`. The short form is the FastMCP
2.x spelling and every stale blog post still shows it.

Programmatic, in-memory — no subprocess, no network, no key:

```bash
python - <<'PY'
import asyncio, sys
sys.path.insert(0, ".")
from fastmcp import Client
from mcp_server import mcp

async def main():
    async with Client(mcp) as c:                     # pass the server object itself
        print([t.name for t in await c.list_tools()])
        r = await c.call_tool("spelling_bee",
                              {"letters": "VALIDTY", "center": "V", "agent_name": "inspector"})
        print(r.data["count"], r.data["total_points"], r.data["pangrams"])

asyncio.run(main())
PY
```

Expected (plus INFO lines on stderr):

```
['spelling_bee']
34 171 ['VALIDITY']
```

---

## 5. Edge case — a puzzle that isn't a puzzle

Six letters instead of seven:

```bash
python agent_with_mcp.py --letters VALIDT --center V
```

The solver raises `ValueError: need exactly 7 distinct letters, got 6`. What
matters is where it lands: the server returns an MCP error result, the adapter
turns it into a `ToolMessage(status="error")`, and the model reads it and
*recovers* instead of the process dying. In an observed run it retried with the
intended 7-letter set and flagged the discrepancy itself:

```
Here's the solution for letters V, A, L, I, D, T, Y with center letter V
(interpreting your puzzle as VALIDTY):
...
Let me know if you actually intended different letters, and I can re-run the puzzle!
```

That recovery is model behaviour, so the exact wording — and whether it retries
at all — will vary between runs. The deterministic half is below.

Same thing at the protocol level, no model involved:

```bash
python - <<'PY'
import asyncio, sys
sys.path.insert(0, ".")
from fastmcp import Client
from mcp_server import mcp

async def main():
    async with Client(mcp) as c:
        r = await c.call_tool("spelling_bee",
                              {"letters": "VALIDT", "center": "V", "agent_name": "inspector"},
                              raise_on_error=False)
        print("is_error:", r.is_error, "|", r.content[0].text)

asyncio.run(main())
PY
```

Expected (a rich traceback also prints to **stderr** — that's deliberate, it
must never touch stdout):

```
is_error: True | Error calling tool 'spelling_bee': need exactly 7 distinct letters, got 6
```

---

## 6. The diff — the actual deliverable of this folder

```bash
diff agent_with_tool.py agent_with_mcp.py
```

Expected: exactly three kinds of change — the solver block deleted, a
`MultiServerMCPClient` added, and `tools = [spelling_bee]` becoming
`tools = await client.get_tools()`. The `create_agent` call, the system prompt,
the `ainvoke`, the argparse flags and the printing are untouched.

And the claim the folder rests on — the solver never changed:

```bash
diff <(sed -n '/^def load_words/,/^    }$/p' agent_with_tool.py) \
     <(sed -n '/^def load_words/,/^    }$/p' mcp_server.py)
```

Expected: **no output.** 36 lines, byte-identical, and identical to
`../shared/solvers_reference.py`. Only the decorator above them differs.
