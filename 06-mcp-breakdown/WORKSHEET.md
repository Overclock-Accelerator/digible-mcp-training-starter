# MCP server dissection worksheet

Ten questions. **None of them can be answered from a README**, and that is the
point — every one is answered by source, by a schema, or by the protocol.

Fill one of these in before you let a third-party MCP server into your context
window. It takes about twenty minutes per server once you have done it twice.

Server: ________________________   Version / commit / date fetched: ________________

Repo or endpoint: ________________________   Date dissected: ________________________

---

## Question 0 — how much of this can you actually see?

Answer this before the other ten, because it decides how much the rest is worth.
Many production servers are hosted and closed; you will not get a `tools/list`
out of them without an account.

Tick what you have:

- [ ] Source code (license: ______________, LOC: ________, last commit: ________)
- [ ] A live `tools/list` you obtained yourself
- [ ] A published tool catalogue in the vendor's docs
- [ ] Public OAuth discovery metadata (`/.well-known/oauth-protected-resource`, `…-authorization-server`)
- [ ] A dated changelog of the tool surface
- [ ] Nothing but a marketing page

> What you could NOT determine, and why:
>
> (Keep this list. It is evidence for the adoption decision, not an apology
> for an incomplete worksheet. "We cannot see the text our model is sent"
> is a finding.)

**For every answer below, write where it came from:** `SOURCE` (you read the
code), `WIRE` (you got it off the protocol), `DOCS` (the vendor says so), or
`UNVERIFIED`.

---

### 1. What does it actually expose?

List every tool, prompt, and resource, by name. Prefer `tools/list` /
`prompts/list` / `resources/list` over the protocol. If you cannot reach the
protocol, use the vendor's catalogue and **say that you did**.

Then count. How many tool definitions land in the context window on a default
connection? At roughly 170–190 input tokens each, what does that cost per
request — and is there a knob (a toolset parameter, a config file, a manual
mode) that changes the number?

> Tools (n = ____ default, ____ maximum):
>
> Prompts:
>
> Resources:
>
> Tokens per request, default vs. maximum:
>
> Any capabilities declared but empty?

---

### 2. What does each tool description literally say?

Paste the description **verbatim**, in full, for each tool. Do not summarize it.
This text is written by a stranger and lands, unaltered, in your model's context
on every conversation where the server is connected.

Then: is any of it addressed to the *model* rather than describing the tool?
Look for "you", "must", "always", "do not", "instead", and for anything that
overrides a prior instruction or belief. And check the adjectives — "read-only",
"safe", "restricted" — against the capability list that follows them.

> Verbatim:
>
> Model-directed language present? Where?
>
> Any adjective the rest of the sentence contradicts?

---

### 3. What is in the parameter schema?

For each tool: how many parameters, how many required, and what does each
parameter's `description` say? Note any parameter whose description carries
instructions rather than a type explanation.

Count the parameters. A tool with fourteen of them and one required is a tool
the model will call wrong, and the wrongness will be your bug.

> Tool → params (n required of m):
>
> Any parameter description that instructs rather than describes:

---

### 4. Are there instructions outside the tool descriptions?

Servers can inject text at least four other ways, and README readers see none:

- server-level `instructions` sent at connect time
- prompts (their name, description, and rendered message content)
- **error and result strings** — an error message is prompt surface too
- **a client plugin, skill, or agent file the vendor ships alongside** — text
  that is not in the server at all, and is absent if you connect the default way

> Server instructions:
>
> Prompt content:
>
> Error strings that address the model:
>
> Vendor-shipped client-side prompt text — and is it opt-in?

---

### 5. Where does state live?

Per-process globals? A session store? A database? Nothing at all (stateless per
request)? What survives a restart, and what does the server remember about you
between calls?

For a hosted server, ask the sharper version: **is the tool list itself state?**
Can it change without you reconnecting — because the vendor shipped, or because
the model or the account changed it?

> State:
>
> Is the tool list mutable at runtime? By whom?
>
> Line reference or doc reference:

---

### 6. How is auth handled — and what happens with none?

Is there any auth? Where is the credential read from (flag, env var, header —
list every spelling accepted, including a URL query parameter)? Is there an
anonymous tier? Is auth enforced per-transport or per-endpoint?

Then read the **OAuth metadata**, which is public even when the server is not:
what scopes exist, and does any of them correspond to a capability you would
actually want to grant separately? Is PKCE required, and is `plain` still
accepted? Can any client self-register?

Then the question people skip: **what does the server do when you provide no
credential at all?** Refuse, degrade, or run fully?

> Credential sources (every accepted spelling):
>
> Scopes offered, and what they actually constrain:
>
> Anonymous behaviour:

---

### 7. What happens on error?

Does a failure come back as a **protocol error** (the client can see it failed)
or as ordinary tool **content** (the model reads the failure as if it were an
answer)? Is there a timeout? Does the error text leak internals — stack traces,
hostnames, keys?

This one matters more than it looks. Errors returned as content get treated by
the model as information.

> Error mechanism:
>
> Timeout:
>
> Leakage:

---

### 8. What does this server send anywhere else?

Follow every outbound call. For each one: what host, what payload, what headers,
and is any of it derived from your environment rather than your request?

For a hosted server the whole thing is an outbound call, so ask instead: what
does the vendor retain, where does it live, for how long, is it used for model
training, and can you get an audit log of every call?

> Outbound hosts / data residency:
>
> Payload (what leaves your machine):
>
> Retention, training use, audit log availability:
>
> Disclosed in the docs? (grep for telemetry / privacy / analytics / training)

---

### 9. What can it reach, and what stops it?

What can this server read, write, execute, or spend on your behalf? Is there any
allowlist, denylist, validation, quota, timeout, or size cap — and where is it
enforced: in the server, in the vendor's platform, or nowhere?

Two specific things to chase, because they are the ones that hurt:

- **Blast radius.** Can it delete, drop, send, or publish? What is the most
  destructive single call available, and what would stop it?
- **Cost.** Can one tool call spend real money — warehouse credits, API quota,
  per-call task charges? Is there a ceiling, and who set it?

Do not assume; find the enforcement code or config, or find that there is none.

> Filesystem / process / network reach:
>
> Most destructive single call available:
>
> Cost per call, and the ceiling (if any):
>
> Config flags or defaults that weaken a guard:

---

### 10. What would you change before adopting it?

Concrete, in priority order. "Wrap it", "pin it", "restrict it at the edge" and
"we would not adopt this" are all legitimate answers.

Then the one people skip: **how would you notice if the tool descriptions
changed next week?** You approved a version; nothing pins you to it.

For a hosted server you cannot pin at all, so answer the replacement question:
which of these three do you actually have, and which will you use?

- [ ] A vendor changelog at tool granularity — subscribe to it
- [ ] A constraint at your edge (toolset parameter, spec file, manual mode, role)
- [ ] Runtime call logging you can review after the fact

> Changes:
>
> Change-detection plan:
>
> Adopt / wrap / restrict / decline:

---

## The pinning question

A server's tool descriptions are fetched fresh at connect time. `npx -y
some-mcp-server` fetches the latest version every launch. A hosted server has no
version at all. So the text you audited and the text your model reads tomorrow
are two different things.

**If the server runs locally and you can reach it**, snapshot it and diff it:

```bash
# Snapshot what the model actually sees, and diff it on every upgrade.
npx -y @modelcontextprotocol/inspector --cli <server-command> \
  --method tools/list > baseline-$(date +%F).json
```

**If it is hosted and you cannot**, write down which of the three replacements
from Q10 you are relying on — and if the answer is "none of them", that belongs
in the adoption decision, not in a footnote.
