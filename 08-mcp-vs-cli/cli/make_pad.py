#!/usr/bin/env python3
"""Generate the CLI arm's pad commands from the shared capability catalogue.

    python cli/make_pad.py

Writes one executable script per entry in `pad_catalog.PAD_TOOLS` into
`cli/pad/`. The MCP server registers the same table as tools, so "40 tools" and
"40 commands" are provably the same 40 capabilities and the two lines on the
chart share an x-axis.

Each script is trivial — it prints real `--help` text and exits — because what
is being measured is the cost of *having* a capability available, not of
running it. What matters is that the help text is realistic: an agent going
looking pays for reading it.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from pad_catalog import PAD_TOOLS  # noqa: E402

PAD_DIR = HERE / "pad"

TEMPLATE = '''#!/usr/bin/env python3
"""{summary}"""
import argparse, sys

p = argparse.ArgumentParser(prog="{command}", description="{summary}")
{arguments}
a = p.parse_args()
print("{command}: not implemented — this is a benchmark pad command.", file=sys.stderr)
raise SystemExit(3)
'''


def _arguments(signature: str) -> list[str]:
    """Turn `word: str, min_length: int = 3` into argparse declarations."""
    out = []
    for part in signature.split(", "):
        name, _, annotation = part.partition(": ")
        annotation, _, default = annotation.partition(" = ")
        flag = "--" + name.strip().replace("_", "-")
        kind = {"int": "int", "bool": "str", "list[str]": "str"}.get(annotation.strip(), "str")
        req = "" if default else ", required=True"
        dflt = f", default={default}" if default else ""
        out.append(f'p.add_argument("{flag}", type={kind}{req}{dflt}, help="{name.strip()}")')
    return out


def main() -> int:
    PAD_DIR.mkdir(exist_ok=True)
    for name, signature, doc in PAD_TOOLS:
        command = name.replace("_", "-")
        # First line of the tool docstring is the human summary; the Args block
        # becomes flags, which is what --help spelunking actually costs to read.
        summary = doc.splitlines()[0].strip().replace('"', "'")
        sig = ", ".join(p for p in signature.split(", ") if not p.startswith("agent_name"))
        script = PAD_DIR / command
        script.write_text(TEMPLATE.format(
            command=command, summary=summary, arguments="\n".join(_arguments(sig))))
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"wrote {len(PAD_TOOLS)} pad commands to {PAD_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
