#!/usr/bin/env bash
# Inspect three production MCP servers -- Zapier, Snowflake, Datadog -- as far as
# is possible with NO account, NO API key and NO signup.
#
#   ./inspect.sh            # everything (deps, probe, oauth, all three, tokens)
#   ./inspect.sh probe      # what the three endpoints do with no credential
#   ./inspect.sh oauth      # public OAuth discovery metadata
#   ./inspect.sh zapier     # Zapier: meta-tool catalogue + plugin source
#   ./inspect.sh snowflake  # Snowflake: managed spec + the deprecated OSS server
#   ./inspect.sh datadog    # Datadog: 265-tool catalogue, toolsets, changelog
#   ./inspect.sh tokens     # the context-window arithmetic, from real counts
#
# READ THIS FIRST. Unlike the previous version of this folder, you CANNOT run
# tools/list against any of these three. All three are hosted and all three
# require credentials before they will say a word. Every command below is
# honest about that: nothing here fakes a protocol dump it did not get.
#
# Downloads land in ./servers/ which is gitignored.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HERE/servers"

ZAPIER_MCP="https://mcp.zapier.com/api/v1/connect"
DATADOG_MCP="https://mcp.datadoghq.com/v1/mcp"
SNOWFLAKE_DOCS="https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp"

hr()  { printf '\n\033[1m── %s\033[0m\n' "$1"; }
note() { printf '\033[2m%s\033[0m\n' "$1"; }

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 — $2" >&2; exit 1; }
}

do_deps() {
  hr "dependencies"
  need curl "ships with macOS; apt install curl on Linux"
  need jq   "brew install jq"
  need git  "install git"
  need python3 "install Python 3.10+"
  echo "  curl, jq, git, python3 — all present"
  note "  No Node, no venv, no API key. Nothing here talks to a model."
}

# ------------------------------------------------------------------ probe

do_probe() {
  hr "what each endpoint does with NO credential"
  note "A well-formed MCP initialize request, sent to each hosted server."

  local INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'

  for U in "$ZAPIER_MCP" "$DATADOG_MCP"; do
    echo
    echo "POST $U"
    curl -sS -m 20 -D - -o /tmp/mcp-probe-body.$$ \
      -X POST "$U" \
      -H 'Content-Type: application/json' \
      -H 'Accept: application/json, text/event-stream' \
      -d "$INIT" \
      | grep -iE '^HTTP/|^www-authenticate:' || true
    echo "  body: $(head -c 300 /tmp/mcp-probe-body.$$)"
    rm -f /tmp/mcp-probe-body.$$
  done

  echo
  echo "Snowflake: there is no shared host to probe."
  echo "  Its endpoint is per-account:"
  echo "  https://<account_url>/api/v2/databases/{database}/schemas/{schema}/mcp-servers/{name}"

  hr "conclusion — write this on your worksheet"
  cat <<'TXT'
  None of the three will return tools/list without credentials.
  You cannot read the wire text. Everything that follows is therefore
  second-hand: published catalogues, OAuth metadata, and source for the one
  server that has any. Treat every tool description you read in the docs as
  "what the vendor documents", not "what the model receives" -- they are
  usually the same and you have no way to prove it.
TXT
}

# ------------------------------------------------------------------ oauth

do_oauth() {
  hr "public OAuth discovery metadata (no credential needed)"
  note "RFC 9728 + RFC 8414. This is the one part of a hosted server that is"
  note "designed to be readable by strangers. Read it before you consent."

  echo
  echo "Zapier — protected resource:"
  curl -sS -m 20 "https://mcp.zapier.com/.well-known/oauth-protected-resource/api/v1/connect" | jq .
  echo "Zapier — authorization server:"
  curl -sS -m 20 "https://mcp.zapier.com/.well-known/oauth-authorization-server" | jq .

  echo
  echo "Datadog — protected resource:"
  curl -sS -m 20 "https://mcp.datadoghq.com/.well-known/oauth-protected-resource/v1/mcp" | jq .
  echo "Datadog — authorization server:"
  curl -sS -m 20 "https://mcp.datadoghq.com/.well-known/oauth-authorization-server" | jq .

  hr "two things to notice"
  cat <<'TXT'
  1. Datadog advertises exactly one scope: "mcp_all". There is no read-only
     grant to consent to. Which of the 265 tools you get is decided by a
     ?toolsets= query parameter that the CLIENT controls, not by the token.
  2. Zapier advertises "openid profile email" -- scopes that describe the
     sign-in, not the app access. Nothing in the consent screen's scope list
     tells you it can send mail from your Gmail.
  Both expose a registration_endpoint, so any client can self-register.
TXT
}

# ------------------------------------------------------------------ zapier

do_zapier() {
  mkdir -p "$DIR"
  hr "Zapier — the tool catalogue Zapier publishes"
  note "docs.zapier.com serves a .md twin of every page. That is machine-readable"
  note "vendor documentation, and it is the closest thing to a manifest you get."

  curl -sSL -m 30 "https://docs.zapier.com/mcp/overview/how-tools-work.md" \
    -o "$DIR/zapier-tools.md"
  sed -n '/^## Meta-tools/,/^## Auto-provisioning/p' "$DIR/zapier-tools.md"

  hr "Zapier — what is on GitHub, and what is not"
  [ -d "$DIR/zapier-mcp" ] || \
    git clone --depth 1 -q https://github.com/zapier/zapier-mcp.git "$DIR/zapier-mcp"
  git -C "$DIR/zapier-mcp" log -1 --format='  commit %h %ci'
  echo "  files that are not markdown, json, or images:"
  find "$DIR/zapier-mcp" -type f -not -path '*/.git/*' \
    -not -name '*.md' -not -name '*.mdc' -not -name '*.json' \
    -not -name '*.png' -not -name '*.svg' -not -name '*.txt' \
    -not -name 'LICENSE' -not -name '.*' | sed 's/^/    /' || true
  echo "  (if that list is empty: there is no server code in this repo at all)"

  hr "Zapier — the safety text, and where it lives"
  sed -n '/^## Safety Rules/,/^## Plugin Skills/p' \
    "$DIR/zapier-mcp/plugins/zapier/agents/zapier-mcp.agent.md"
  note "That is genuinely good prompt-injection defence. Now note the path it"
  note "came from: plugins/zapier/agents/. It is an OPTIONAL plugin, not the"
  note "server. The documented default is OAuth from inside your client, with"
  note "no plugin -- in which case none of that text exists and nothing in the"
  note "protocol makes execute_zapier_write_action ask you first."

  hr "Zapier — is there a changelog for the MCP tool surface?"
  echo -n "  docs.zapier.com/mcp/changelog.md → HTTP "
  curl -sSL -m 20 -o /dev/null -w '%{http_code}\n' "https://docs.zapier.com/mcp/changelog.md"
  echo "  changelogs listed in llms.txt:"
  curl -sSL -m 20 "https://docs.zapier.com/llms.txt" | grep -i 'changelog' | sed 's/^/    /' || true
  note "  Changelogs exist for the SDK and the Developer Platform. None for MCP."
}

# ------------------------------------------------------------------ snowflake

do_snowflake() {
  mkdir -p "$DIR"
  hr "Snowflake — the OFFICIAL server is a database object, not a package"
  note "You do not install it. You CREATE it, and you write the tool descriptions."
  curl -sSL -m 40 "$SNOWFLAKE_DOCS" -o "$DIR/snowflake-docs.html"
  echo "  fetched $(wc -c < "$DIR/snowflake-docs.html" | tr -d ' ') bytes of docs"
  python3 - "$DIR/snowflake-docs.html" <<'PY'
import html, re, sys
text = html.unescape(re.sub(r'<[^>]+>', ' ', open(sys.argv[1], encoding='utf-8',
                                                  errors='replace').read()))
def count(term):
    return len(re.findall(re.escape(term), text))

print("\n  the privilege model, extracted from the page:")
m = re.search(r'Privilege\s+Object\s+Description(.{0,900}?)Grant access', text, re.S)
if m:
    for row in re.findall(
            r'(CREATE|OWNERSHIP|MODIFY|USAGE|SELECT)\s+([A-Za-z ()\-]+?)\s\s+([^|]{10,90}?)\s\s',
            m.group(1)):
        print(f"    {row[0]:<10} {row[1].strip():<34} {row[2].strip()}")
else:
    print("    (privilege table not found — the docs page changed)")
print("    ^ USAGE on the MCP SERVER only gets you connect + tools/list.")
print("      Every tool needs its own grant, separately.")

print("\n  the five tool types, and how often each appears on the page:")
for t in ("CORTEX_AGENT_RUN", "CORTEX_SEARCH_SERVICE_QUERY",
          "CORTEX_ANALYST_MESSAGE", "SYSTEM_EXECUTE_SQL", "GENERIC"):
    print(f"    {t:<28} {count(t):>3}")

print("\n  the cost and blast-radius knobs, confirmed present:")
for k in ("read_only", "query_timeout", "warehouse", "250 KB",
          "maximum of 50 tools", "recursion depth"):
    print(f"    {k:<22} {count(k):>3}")

for phrase in ("When set to", "Snowflake-managed MCP server does not support",
               "Higher tool counts", "allows the MCP client to bypass"):
    m = re.search(re.escape(phrase) + r'[^.]*\.', text)
    if m:
        print("\n    > " + " ".join(m.group(0).split()))
PY
  note "  Full text and verbatim quotes: README.md, Snowflake section."

  hr "Snowflake — the one server of the three with readable source (DEPRECATED)"
  [ -d "$DIR/snowflake-labs-mcp" ] || \
    git clone --depth 1 -q https://github.com/Snowflake-Labs/mcp.git "$DIR/snowflake-labs-mcp"
  git -C "$DIR/snowflake-labs-mcp" log -1 --format='  commit %h %ci'
  head -5 "$DIR/snowflake-labs-mcp/README.md" | sed 's/^/  /'
  echo
  find "$DIR/snowflake-labs-mcp/mcp_server_snowflake" -name '*.py' | sort | xargs wc -l | tail -1

  hr "the entire description of a tool that runs arbitrary DDL"
  cat "$DIR/snowflake-labs-mcp/mcp_server_snowflake/query_manager/prompts.py"
  note "Four lines. No cost warning, no row limit, no 'this can drop a table'."

  hr "the gate that IS there — one middleware, ahead of every tool call"
  sed -n '9,46p' "$DIR/snowflake-labs-mcp/mcp_server_snowflake/server_utils.py"

  hr "and the permissions the shipped example config hands it"
  sed -n '36,54p' "$DIR/snowflake-labs-mcp/services/configuration.yaml"
  note "Read that list again. Drop: True. Delete: True. TruncateTable: True."
  note "That is the template an operator copies."

  hr "a source comment worth reading twice"
  sed -n '293,308p' "$DIR/snowflake-labs-mcp/mcp_server_snowflake/object_manager/tools.py"
  note "Alter: False does NOT block create_or_alter_object. Create: True allows it."

  hr "how much cost control is in this file?"
  grep -nE 'LIMIT|timeout|warehouse|max_rows|bytes_scanned' \
    "$DIR/snowflake-labs-mcp/mcp_server_snowflake/query_manager/tools.py" \
    || echo "  (no matches — there is none)"
}

# ------------------------------------------------------------------ datadog

do_datadog() {
  mkdir -p "$DIR"
  hr "Datadog — the published tool catalogue"
  note "docs.datadoghq.com also serves .md twins. This one is 130+ KB."
  curl -sSL -m 60 "https://docs.datadoghq.com/mcp_server/tools.md" -o "$DIR/datadog-tools.md"
  curl -sSL -m 60 "https://docs.datadoghq.com/mcp_server/setup.md" -o "$DIR/datadog-setup.md"
  echo "  tools.md: $(wc -l < "$DIR/datadog-tools.md" | tr -d ' ') lines"

  python3 - "$DIR/datadog-tools.md" "$DIR/datadog-setup.md" <<'PY'
import re, sys, collections
tools_md, setup_md = (open(p, encoding='utf-8').read() for p in sys.argv[1:3])

tools = {}
for b in re.split(r'^### `', tools_md, flags=re.M)[1:]:
    name = re.match(r'([A-Za-z0-9_]+)`', b).group(1)
    m = re.search(r'\*Toolset: \*\*(.+?)\*\*\*', b)
    tools[name] = {x.strip('* ').strip()
                   for x in re.split(r'\*\*,\s*\*\*|,\s*', m.group(1))} if m else set()

labels = collections.Counter(t for ts in tools.values() for t in ts)
ga = set(re.findall(r'^- `([a-z0-9-]+)`:', setup_md[
    setup_md.index('### Available toolsets'):setup_md.index('### Preview toolsets')], re.M))
pv = set(re.findall(r'^- `([a-z0-9-]+)`:', setup_md[setup_md.index('### Preview toolsets'):], re.M))

print(f"\n  {len(tools)} documented tools, carrying {len(labels)} distinct toolset labels")
print(f"  setup.md offers {len(ga)} generally-available toolsets + {len(pv)} in Preview\n")
for k, v in labels.most_common():
    tag = "" if k in ga else ("  (Preview)" if k in pv else "  (!! not listed in setup.md)")
    print(f"    {k:<22} {v:>3}  {'#' * v}{tag}")

print(f"\n  default (no query param)      = core           = {labels['core']:>3} tools")
print(f"  ?toolsets=all                 = the {len(ga)} GA sets = "
      f"{sum(1 for ts in tools.values() if ts & ga):>3} tools")
print(f"  everything documented         = +Preview       = {len(tools):>3} tools")

orphan = {k: v for k, v in labels.items() if k not in ga | pv}
missing = (ga | pv) - set(labels)
if orphan or missing:
    print("\n  doc drift, found by diffing the two pages against each other:")
    for k, v in sorted(orphan.items()):
        print(f"    {v:>3} tools are labelled `{k}`, which setup.md never offers as a toolset")
    for k in sorted(missing):
        print(f"    `{k}` is offered as a toolset, but no tool on this page is labelled with it")
    print("    Neither page is wrong. Nothing makes them agree.")
PY

  hr "the default is the core toolset. the knob is a query parameter."
  sed -n '/^### Available toolsets/,/^### Preview toolsets/p' "$DIR/datadog-setup.md" | head -8
  grep -n 'consumes context window space' "$DIR/datadog-setup.md" | sed 's/^/  /'
  note "Datadog documents the context-window cost of its own tool surface."
  note "That is the single best thing any of these three vendors does."

  hr "two tool descriptions to read out loud"
  python3 - "$DIR/datadog-tools.md" <<'PY'
import re, sys
s = open(sys.argv[1], encoding='utf-8').read()
for name in ('datadog_remote_action_restricted_shell_run_command',
             'create_datadog_monitor'):
    m = re.search(r'^### `' + name + r'`.*?(?=^### |^## )', s, re.M | re.S)
    if m:
        print('\n' + '-' * 68)
        print(m.group(0).strip()[:1400])
PY
  note "One says 'read-only' and then lists sed and find, grants pipes, loops and"
  note "globbing, and offers to cat the file holding your Datadog API key."
  note "The other creates monitors in draft mode with notifications off and hands"
  note "the publish step to a human in the UI. Same server, same week."

  hr "Datadog — the one public tool-surface changelog of the three"
  [ -d "$DIR/datadog-mcp-server" ] || \
    git clone --depth 1 -q https://github.com/datadog-labs/mcp-server.git "$DIR/datadog-mcp-server"
  git -C "$DIR/datadog-mcp-server" log -1 --format='  commit %h %ci'
  echo "  CHANGELOG.md: $(grep -c '^## ' "$DIR/datadog-mcp-server/CHANGELOG.md" | tr -d ' ') dated entries"
  echo "  newest: $(grep -m1 '^## ' "$DIR/datadog-mcp-server/CHANGELOG.md")"
  echo "  oldest: $(grep '^## ' "$DIR/datadog-mcp-server/CHANGELOG.md" | tail -1)"
  echo
  sed -n '3,10p' "$DIR/datadog-mcp-server/CHANGELOG.md"
  note "You cannot pin a hosted server. A changelog at tool granularity is the"
  note "next best thing, and it is the only reason you would ever notice a change."
}

# ------------------------------------------------------------------ tokens

do_tokens() {
  [ -f "$DIR/datadog-tools.md" ] || do_datadog >/dev/null
  hr "the 07 arithmetic, on real numbers"
  python3 - "$DIR/datadog-tools.md" "$DIR/datadog-setup.md" <<'PY'
import re, sys
tools_md, setup_md = (open(p, encoding='utf-8').read() for p in sys.argv[1:3])
tools = {}
for b in re.split(r'^### `', tools_md, flags=re.M)[1:]:
    name = re.match(r'([A-Za-z0-9_]+)`', b).group(1)
    m = re.search(r'\*Toolset: \*\*(.+?)\*\*\*', b)
    tools[name] = {x.strip('* ').strip()
                   for x in re.split(r'\*\*,\s*\*\*|,\s*', m.group(1))} if m else set()
ga = set(re.findall(r'^- `([a-z0-9-]+)`:', setup_md[
    setup_md.index('### Available toolsets'):setup_md.index('### Preview toolsets')], re.M))

n_core = sum(1 for ts in tools.values() if 'core' in ts)
n_ga   = sum(1 for ts in tools.values() if ts & ga)
rows = [
    ("Zapier    14 meta-tools, fixed",                     14),
    ("Datadog   default, no query param (core)",       n_core),
    ("Datadog   ?toolsets=all",                          n_ga),
    ("Datadog   every documented tool",             len(tools)),
    ("Snowflake documented cap, one server",               50),
]
print("\n  07 measured ~170-190 input tokens per tool definition, per request.\n")
print(f"  {'server / configuration':<44}{'tools':>6}{'tokens per request':>24}")
print("  " + "-" * 72)
for label, n in rows:
    print(f"  {label:<44}{n:>6}{n*170:>12,} - {n*190:<10,}")
print("""
  Same protocol, same week. Datadog alone spans 10x, decided by a query
  parameter; across all three servers the spread is nearly 20x.

  And Zapier's 40,000 actions would be roughly 7 MILLION tokens if it shipped
  one tool per action. It ships 14 meta-tools instead and makes the model
  search at runtime. That is the whole design, and it is a trade: context
  tokens down, round-trips up, and the tool set you approved at connect time
  is not the tool set you have three turns later.""")
PY
}

case "${1:-all}" in
  deps)      do_deps ;;
  probe)     do_probe ;;
  oauth)     do_oauth ;;
  zapier)    do_zapier ;;
  snowflake) do_snowflake ;;
  datadog)   do_datadog ;;
  tokens)    do_tokens ;;
  all)       do_deps; do_probe; do_oauth; do_zapier; do_snowflake; do_datadog; do_tokens ;;
  *) echo "usage: $0 [deps|probe|oauth|zapier|snowflake|datadog|tokens|all]" >&2; exit 1 ;;
esac
