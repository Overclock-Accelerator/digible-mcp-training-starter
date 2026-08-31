"""Load environment variables from a .env.local file.

Convention for this repo: put your key in `.env.local` at the repo root.

    ANTHROPIC_API_KEY=sk-ant-...

`.env.local` is gitignored. Every agent calls `load_env()` before it reads
`ANTHROPIC_API_KEY`, so nothing here ever needs the key exported in a shell.

Deliberately dependency-free -- this is twenty lines, and adding python-dotenv
to teach MCP would be one more thing to install and go wrong in a live session.
Real values already in the environment always win, so `export` still overrides
the file.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

FILENAMES = (".env.local", ".env")


def _caller_dir() -> Path:
    """Directory of the file that called into this module.

    Defaulting to Path.cwd() was a real bug: an agent run from outside the
    repo would fail to find a perfectly good .env.local. Anchoring to the
    calling file means `load_env()` works from any working directory.
    """
    for frame in inspect.stack()[1:]:
        filename = frame.filename
        if filename != __file__ and not filename.startswith("<"):
            return Path(filename).resolve().parent
    return Path.cwd()


def find_env_file(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default: the caller's directory) for .env.local, then .env."""
    here = (start or _caller_dir()).resolve()
    for directory in (here, *here.parents):
        for name in FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_env(start: Path | None = None) -> Path | None:
    """Load KEY=VALUE lines into os.environ. Returns the file used, if any.

    Existing environment variables are never overwritten.
    """
    path = find_env_file(start or _caller_dir())
    if path is None:
        return None

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return path


def require(name: str = "ANTHROPIC_API_KEY") -> str:
    """Return an env var, or exit with instructions on how to set it."""
    load_env(_caller_dir())
    value = os.environ.get(name)
    if not value:
        root = Path(__file__).resolve().parent.parent
        raise SystemExit(
            f"error: {name} is not set.\n"
            f"  Create {root / '.env.local'} containing:\n"
            f"    {name}=your-key-here\n"
            f"  (or export {name} in your shell)"
        )
    return value
