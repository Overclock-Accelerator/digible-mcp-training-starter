#!/usr/bin/env bash
# Stop the five MCP servers started by ./start_servers.sh.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$HERE/servers/.pids"

if [ ! -f "$PIDFILE" ]; then
  echo "no $PIDFILE — nothing started by ./start_servers.sh" >&2
  exit 0
fi

while read -r pid; do
  [ -n "$pid" ] || continue
  if kill "$pid" 2>/dev/null; then
    echo "  stopped pid $pid"
  fi
done < "$PIDFILE"

rm -f "$PIDFILE"
echo "all stopped."
