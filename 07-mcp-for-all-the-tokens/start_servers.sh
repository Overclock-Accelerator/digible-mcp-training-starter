#!/usr/bin/env bash
# Start all five vendors' MCP servers, one process each, on ports 8010-8014.
#
#     ./start_servers.sh          # start them, log to servers/logs/
#     ./stop_servers.sh           # stop them
#
# Elsewhere in this repo a server gets its own terminal, and you should do that
# here too for one or two of them -- watching a call land in the Bastion window
# is the whole point. But five terminals is a lot to ask of a room, so this
# starts all five in the background and tees each one's log to a file you can
# `tail -f`. Run the two you care about by hand instead if you prefer:
#
#     python servers/server.py --server northwind-docs
#     python servers/server.py --server bastion-infra
#
# The agent NEVER spawns these. It connects by URL and fails with instructions
# if they are not up.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-$HERE/../.venv/bin/python}"
LOGS="$HERE/servers/logs"
PIDFILE="$HERE/servers/.pids"

[ -x "$PY" ] || { echo "error: no interpreter at $PY (set PYTHON=...)" >&2; exit 1; }

# Idempotent: running this twice is a no-op, not an error. A stale pidfile from
# a crashed or manually-killed run is cleaned up rather than treated as live.
if [ -f "$PIDFILE" ]; then
  live=0
  while read -r pid; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && live=$((live + 1))
  done < "$PIDFILE"
  if [ "$live" -gt 0 ]; then
    echo "already running ($live server(s)); nothing to do."
    echo "  ./stop_servers.sh   to stop them"
    exit 0
  fi
  rm -f "$PIDFILE"
fi

# A port held by something else is worth catching here rather than as a
# connection error in the agent twenty seconds later.
for port in 8010 8011 8012 8013 8014; do
  if nc -z 127.0.0.1 "$port" 2>/dev/null; then
    echo "error: port $port is already in use by another process" >&2
    exit 1
  fi
done

mkdir -p "$LOGS"
: > "$PIDFILE"

# Order matters only for readability here; the agent decides its own order.
for entry in northwind-docs:8010 helios-helpdesk:8011 meridian-crm:8012 \
             lumen-analytics:8013 bastion-infra:8014; do
  name="${entry%%:*}"
  port="${entry##*:}"
  "$PY" "$HERE/servers/server.py" --server "$name" --port "$port" \
      > "$LOGS/$name.log" 2>&1 &
  echo $! >> "$PIDFILE"
  printf '  %-18s http://127.0.0.1:%s/mcp   (log: servers/logs/%s.log)\n' \
      "$name" "$port" "$name"
done

# Wait for all five to answer before returning, so the next command in a demo
# does not race the servers coming up.
for port in 8010 8011 8012 8013 8014; do
  for _ in $(seq 40); do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then break; fi
    sleep 0.25
  done
done

echo
echo "five servers up. now, in another terminal:"
echo "    python agent.py --servers 5        # chat with all 155 tools"
echo "    python agent.py --servers 1        # chat with just 5"
echo "    tail -f servers/logs/bastion-infra.log   # watch calls arrive"
