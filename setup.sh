#!/usr/bin/env bash
# One-time setup for the mcp-training repo. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || { echo "Python 3.10+ required (fastmcp and langchain both need it)"; exit 1; }

[ -d .venv ] || python3 -m venv .venv
./.venv/bin/python -m pip install -q --upgrade pip
./.venv/bin/python -m pip install -q -r requirements.txt

# The word list is committed, but re-fetch if it went missing.
if [ ! -s shared/data/enable1.txt ]; then
  echo "fetching ENABLE1 word list..."
  curl -sL -o shared/data/enable1.txt \
    https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt
fi

./.venv/bin/python shared/test_solvers.py

echo
echo "Setup complete."
echo
echo "Put your key in .env.local:     cp .env.local.example .env.local"
echo "Then run any agent with:        ./.venv/bin/python <folder>/<agent>.py"
echo "  e.g.  ./.venv/bin/python 01-mcp-bee/agent_with_mcp.py"
echo
echo "(Activating is optional: source .venv/bin/activate)"

