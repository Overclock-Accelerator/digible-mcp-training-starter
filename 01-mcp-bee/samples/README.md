# Sample runs

Commands are from the repo root, with the virtualenv active. Start the server
first in another terminal: `python 01-mcp-bee/mcp_server.py`.

## 1. The local-tool agent

```bash
python 01-mcp-bee/agent_with_tool.py
```

```
- **Word count:** 34
- **Total points:** 171
- **Pangram:** VALIDITY (15 pts)
```

On stderr:

```
INFO bee: spelling_bee letters=VALIDTY center=V agent_name=bee-agent
```

The full list starts `VALIDITY 15, ADDITIVITY 10, AVADAVAT 8, LAVALAVA 8,
LIVIDITY 8, VITALITY 8, …` and ends with the ten 4-letter words at 1 point each
(`AVID, DAVY, DIVA, LAVA, TIVY, VAIL, VIAL, VILL, VITA, VIVA`).

## 2. The MCP agent

```bash
python 01-mcp-bee/agent_with_mcp.py
```

Same 34 / 171 / VALIDITY, same 34-row table. On stderr:

```
INFO  Starting MCP server 'spelling-bee' with transport 'stdio'
INFO  mcp.server.lowlevel.server: Processing request of type ListToolsRequest
INFO  mcp.server.lowlevel.server: Processing request of type CallToolRequest
INFO  bee: spelling_bee letters=VALIDTY center=V agent_name=bee-agent
```

## 3. A different puzzle

```bash
python 01-mcp-bee/agent_with_tool.py --letters CAPITOL --center C
python 01-mcp-bee/agent_with_mcp.py  --letters CAPITOL --center C
```

Both: **136 words, 737 points**, seven pangrams — `APOLITICAL, OCCIPITAL,
POLITICAL, CAPITOL, COALPIT, OPTICAL, TOPICAL`.

## 4. The server on its own, no API key

```bash
fastmcp inspect 01-mcp-bee/mcp_server.py
```

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

```bash
fastmcp dev inspector 01-mcp-bee/mcp_server.py
```

In-memory, no subprocess and no key:

```bash
cd 01-mcp-bee
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

```
['spelling_bee']
34 171 ['VALIDITY']
```

## 5. Six letters instead of seven

```bash
python 01-mcp-bee/agent_with_mcp.py --letters VALIDT --center V
```

The model reads the error and recovers. An observed run:

```
Here's the solution for letters V, A, L, I, D, T, Y with center letter V
(interpreting your puzzle as VALIDTY):
...
Let me know if you actually intended different letters, and I can re-run the puzzle!
```

The same thing at the protocol level:

```bash
cd 01-mcp-bee
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

```
is_error: True | Error calling tool 'spelling_bee': need exactly 7 distinct letters, got 6
```

A rich traceback also prints to stderr.

## 6. The diffs

```bash
diff 01-mcp-bee/agent_with_tool.py 01-mcp-bee/agent_with_mcp.py
```

Three kinds of change: the solver block deleted, a `MultiServerMCPClient` added,
and `tools = [spelling_bee]` becoming `tools = await client.get_tools()`.

```bash
diff <(sed -n '/^def load_words/,/^    }$/p' 01-mcp-bee/agent_with_tool.py) \
     <(sed -n '/^def load_words/,/^    }$/p' 01-mcp-bee/mcp_server.py)
```

Prints nothing.
