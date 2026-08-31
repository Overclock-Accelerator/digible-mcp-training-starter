#!/usr/bin/env python3
"""Tour Trends — where did tour bookings fall off, and by how much?

    python agent_tour_trends.py
    python agent_tour_trends.py "which properties saw tours drop in June?"

DATA ACCESS STYLE: pull the tables into memory once, then do everything in
Python. Written by somebody who is fluent in Python and rusty in SQL, and it
works fine at this size — 4,620 tours and 20,131 leads. It is also the third
implementation of "leads for a property in a month" in this folder.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from langchain_core.tools import tool

# ─── plumbing ────────────────────────────────────────────────────────────────
# Identical in all six agents. Put the repo's shared/ on the path, load the key
# from .env.local, and import create_agent with a readable error if the wrong
# interpreter is active. None of it is about this agent — skim past it.
import argparse
import sys
from pathlib import Path


def _shared_dir() -> Path:
    """Walk up until shared/envloader.py turns up — never count directory levels."""
    for d in Path(__file__).resolve().parents:
        if (d / "shared" / "envloader.py").is_file():
            return d / "shared"
    raise SystemExit("could not find shared/envloader.py — run this from "
                     "inside the mcp-training repo.")


sys.path.insert(0, str(_shared_dir()))
import repl  # noqa: E402
from envloader import load_env, require  # noqa: E402

load_env()

try:
    from langchain.agents import create_agent  # noqa: E402
except ModuleNotFoundError as exc:                     # wrong interpreter
    _root = Path(__file__).resolve().parent.parent.parent
    raise SystemExit(
        f"error: {exc.name} is not installed in the Python you just used.\n"
        f"  This usually means a different virtualenv is active.\n"
        f"  Run it with the repo's own interpreter:\n"
        f"    {_root}/.venv/bin/python {Path(sys.argv[0]).name}\n"
        f"  (or from the repo root: ./setup.sh && source .venv/bin/activate)"
    ) from None
# ─── end plumbing ────────────────────────────────────────────────────────────


DB_FILE = Path(__file__).resolve().parent.parent / "digible.db"

_CACHE: dict[str, list[dict]] = {}


def load(table: str) -> list[dict]:
    """Read a whole table into a list of dicts, once per process."""
    if table not in _CACHE:
        if not DB_FILE.exists():
            raise SystemExit(f"error: {DB_FILE} not found")
        con = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            _CACHE[table] = [dict(r) for r in con.execute(f"SELECT * FROM {table}")]
        finally:
            con.close()
    return _CACHE[table]


def property_by_id() -> dict[int, dict]:
    return {p["property_id"]: p for p in load("properties")}


def find_property(text: str) -> dict | None:
    """Substring match on the property directory, or None for 'all of them'."""
    if not text:
        return None
    needle = text.strip().lower()
    hits = [p for p in load("properties") if needle in p["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ValueError(f"no property matching {text!r}")
    raise ValueError(f"{text!r} matches several: "
                     + ", ".join(p["name"] for p in hits))


def as_month(stamp: str) -> str:
    """'2026-05-14T09:11:02' -> '2026-05'. Timestamps are already ISO."""
    return stamp[:7]


def month_shift(month: str, back: int) -> str:
    """'2026-05' shifted `back` months earlier."""
    year, mon = int(month[:4]), int(month[5:7])
    total = year * 12 + (mon - 1) - back
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def normalise_month(text: str) -> str:
    """Read a month out of ordinary language. Defaults the year to 2026."""
    raw = (text or "").strip().lower()
    names = ["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"]
    digits = [t for t in raw.replace("-", " ").replace("/", " ").split()
              if t.isdigit()]
    year = next((d for d in digits if len(d) == 4), "2026")
    for i, name in enumerate(names, start=1):
        if name[:3] in raw:
            return f"{year}-{i:02d}"
    two = [d for d in digits if len(d) <= 2]
    if two:
        return f"{year}-{int(two[0]):02d}"
    raise ValueError(f"could not read a month out of {text!r}")


def months_with_tours() -> list[str]:
    return sorted({as_month(t["scheduled_at"]) for t in load("tours")})


@tool
def tour_volume(month: str, compare_to_prior: bool = True) -> str:
    """Tours scheduled per property for a month, optionally against the month before.

    month: 'June', '2026-06'.
    compare_to_prior: show the change vs the previous month.
    """
    try:
        month = normalise_month(month)
    except ValueError as exc:
        return str(exc)
    prior = month_shift(month, 1)
    props = property_by_id()

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for tour in load("tours"):
        m = as_month(tour["scheduled_at"])
        if m in (month, prior):
            counts[props[tour["property_id"]]["name"]][m] += 1

    if not counts:
        return (f"no tours in {month}. Months with tours: "
                + ", ".join(months_with_tours()))

    rows = []
    for name, by_month in counts.items():
        now, before = by_month.get(month, 0), by_month.get(prior, 0)
        delta = ((now - before) / before * 100) if before else None
        rows.append((name, now, before, delta))
    rows.sort(key=lambda r: (r[3] if r[3] is not None else 0))

    header = (f"Tours scheduled — {month}"
              + (f" vs {prior}" if compare_to_prior else ""))
    lines = [header]
    for name, now, before, delta in rows:
        if not compare_to_prior:
            lines.append(f"  {name:<28} {now:>4}")
            continue
        change = "  n/a" if delta is None else f"{delta:>+6.1f}%"
        mark = " ← drop" if delta is not None and delta <= -10 else ""
        lines.append(f"  {name:<28} {before:>4} → {now:>4}  {change}{mark}")
    return "\n".join(lines)


@tool
def tour_booking_rate(month: str, property_name: str = "") -> str:
    """What share of a month's leads booked a tour, and what share showed up.

    Leads are counted by creation date; a tour counts for the lead that booked
    it whenever the tour was scheduled.
    """
    try:
        month = normalise_month(month)
        prop = find_property(property_name)
    except ValueError as exc:
        return str(exc)

    pid = prop["property_id"] if prop else None
    lead_ids = {l["lead_id"] for l in load("leads")
                if as_month(l["created_at"]) == month
                and (pid is None or l["property_id"] == pid)}
    if not lead_ids:
        return f"no leads in {month}" + (f" at {prop['name']}" if prop else "")

    booked, completed, no_shows = set(), 0, 0
    for tour in load("tours"):
        if tour["lead_id"] in lead_ids:
            booked.add(tour["lead_id"])
            if tour["completed_at"]:
                completed += 1
            if tour["no_show"]:
                no_shows += 1

    scope = prop["name"] if prop else "portfolio"
    pct = len(booked) / len(lead_ids) * 100
    show_rate = (completed / (completed + no_shows) * 100) if (completed + no_shows) else 0.0
    return (f"Tour booking — {scope}, {month}\n"
            f"  leads              {len(lead_ids):>6}\n"
            f"  booked a tour      {len(booked):>6}  ({pct:.1f}% of leads)\n"
            f"  tours completed    {completed:>6}\n"
            f"  no-shows           {no_shows:>6}  (show rate {show_rate:.1f}%)")


@tool
def tour_types(month: str) -> str:
    """Split a month's tours by type — in person, self guided, live or recorded video."""
    try:
        month = normalise_month(month)
    except ValueError as exc:
        return str(exc)
    tally: dict[str, int] = defaultdict(int)
    for tour in load("tours"):
        if as_month(tour["scheduled_at"]) == month:
            tally[tour["tour_type"]] += 1
    if not tally:
        return f"no tours in {month}"
    total = sum(tally.values())
    lines = [f"Tour types — {month} ({total} tours)"]
    for kind, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {kind:<20} {n:>5}  {n / total * 100:>5.1f}%")
    return "\n".join(lines)


SYSTEM = """You are Digible's tour trends analyst. Account managers come to you when a
property's leasing team says the tour calendar has gone quiet.

A drop is meaningful at 10% month over month or worse. Say which properties
dropped and by how much before you speculate about why.

Always use your tools; never estimate a number yourself.
The data covers 14 properties, January through June 2026. If someone asks for a
month outside that, say so rather than guessing.
Be concise and lead with the number."""

TOOLS = [tour_volume, tour_booking_rate, tour_types]


async def main() -> int:
    # ─── plumbing ───────────────────────────────────────────────────────────
    # Free text, and nothing else. No --property, no --month, no defaults:
    # wiring an example value into argparse would mean the *caller* did the
    # interpreting. No arguments opens a chat; a question answers once.
    ap = argparse.ArgumentParser(description="Tour booking trends.")
    ap.add_argument("question", nargs="*",
                    help="ask in plain English; omit entirely to open a chat")
    args = ap.parse_args()
    # ─── end plumbing ───────────────────────────────────────────────────────
    require("ANTHROPIC_API_KEY")

    # --- the agent, built here so you can actually see it ------------------
    # Six agents in this folder, six copies of these five lines. That is the
    # cheapest duplication here, and nobody would bother extracting it --
    # which is exactly how the expensive duplication above it survives.
    agent = create_agent(
        model="anthropic:claude-sonnet-5",
        tools=TOOLS,
        system_prompt=SYSTEM,
    )

    # ainvoke, not invoke: this stays true once the tools move behind MCP and
    # arrive as coroutine-only StructuredTools.
    if repl.one_shot(args, "question"):
        print(await repl.once(agent, " ".join(args.question)))
        return 0
    return await repl.chat(agent, title="Digible — Tour Trends", hints=["which properties saw tours drop in June?",
               "what share of May's leads at Legacy Trails booked a tour?",
               "how many of June's tours were self guided?"])


if __name__ == "__main__":
    raise SystemExit(repl.run(main()))
