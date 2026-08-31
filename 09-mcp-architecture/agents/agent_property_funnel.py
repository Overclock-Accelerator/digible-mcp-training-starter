#!/usr/bin/env python3
"""Property Funnel — leads to tours to applications to leases, for one property.

    python agent_property_funnel.py
    python agent_property_funnel.py "show me the funnel for Legacy Trails in May"

DATA ACCESS STYLE: a fresh connection per call, closed on the way out, and its
own way of finding the database file — walk up from here until `digible.db`
turns up. Defensive, stateless, perfectly reasonable. It is also the fourth
file in this folder that knows how to find `digible.db` and the fourth that
turns a month into a pair of dates.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, timedelta
from functools import lru_cache

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


@lru_cache(maxsize=1)
def database() -> Path:
    """Walk up from this file until digible.db turns up."""
    for folder in Path(__file__).resolve().parents:
        candidate = folder / "digible.db"
        if candidate.is_file():
            return candidate
    raise SystemExit("error: digible.db not found in any parent directory")


def open_ro() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{database()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def window(period: str) -> tuple[str, str]:
    """Inclusive ISO date bounds for 'YYYY-MM', 'Month', or 'YYYY-MM-DD..YYYY-MM-DD'."""
    text = (period or "").strip()
    if ".." in text:
        first, _, last = text.partition("..")
        return first.strip(), last.strip()

    names = ("jan feb mar apr may jun jul aug sep oct nov dec").split()
    lowered = text.lower()
    year, month = 2026, None
    for chunk in lowered.replace("-", " ").replace("/", " ").split():
        if chunk.isdigit() and len(chunk) == 4:
            year = int(chunk)
        elif chunk.isdigit():
            month = int(chunk)
        elif chunk[:3] in names:
            month = names.index(chunk[:3]) + 1
    if month is None:
        raise ValueError(f"could not read a period out of {period!r}")

    first_day = date(year, month, 1)
    next_first = date(year + (month == 12), month % 12 + 1, 1)
    return first_day.isoformat(), (next_first - timedelta(days=1)).isoformat()


def resolve_property(con, text: str) -> tuple[int, str]:
    """Exact, then case-insensitive, then substring."""
    rows = con.execute(
        "SELECT property_id, name FROM properties ORDER BY name").fetchall()
    needle = (text or "").strip().lower()
    if not needle:
        raise ValueError("which property? " + ", ".join(r["name"] for r in rows))
    for r in rows:
        if r["name"].lower() == needle:
            return r["property_id"], r["name"]
    hits = [r for r in rows if needle in r["name"].lower()]
    if len(hits) == 1:
        return hits[0]["property_id"], hits[0]["name"]
    if not hits:
        raise ValueError(f"no property matching {text!r}. Known: "
                         + ", ".join(r["name"] for r in rows))
    raise ValueError(f"{text!r} matches " + ", ".join(r["name"] for r in hits))


@tool
def funnel(property_name: str, period: str) -> str:
    """Full funnel for one property over a period.

    property_name: 'Legacy Trails' — partial names are matched.
    period: '2026-05', 'May', or an explicit '2026-04-01..2026-06-30'.

    Counts leads created, tours scheduled and completed, applications submitted
    and approved, and NEW leases signed. Renewals are excluded from the lease
    count: no marketing dollar acquired one.
    """
    with closing(open_ro()) as con:
        try:
            pid, name = resolve_property(con, property_name)
            first, last = window(period)
        except ValueError as exc:
            return str(exc)

        leads = con.execute(
            "SELECT COUNT(*) FROM leads WHERE property_id = ? "
            "AND date(created_at) BETWEEN ? AND ?", (pid, first, last)).fetchone()[0]
        tours, completed = con.execute(
            "SELECT COUNT(*), SUM(completed_at IS NOT NULL) FROM tours "
            "WHERE property_id = ? AND date(scheduled_at) BETWEEN ? AND ?",
            (pid, first, last)).fetchone()
        apps, approved = con.execute(
            "SELECT COUNT(*), SUM(status = 'approved') FROM applications "
            "WHERE property_id = ? AND date(submitted_at) BETWEEN ? AND ?",
            (pid, first, last)).fetchone()
        leases = con.execute(
            "SELECT COUNT(*) FROM leases WHERE property_id = ? AND is_renewal = 0 "
            "AND signed_date BETWEEN ? AND ?", (pid, first, last)).fetchone()[0]

    def rate(part: int, whole: int) -> str:
        return f"{part / whole * 100:5.1f}% of leads" if whole else "    —"

    return "\n".join([
        f"Funnel — {name}, {first} to {last}",
        f"  leads                {leads:>6}",
        f"  tours scheduled      {tours:>6}   {rate(tours, leads)}",
        f"  tours completed      {completed or 0:>6}   {rate(completed or 0, leads)}",
        f"  applications         {apps:>6}   {rate(apps, leads)}",
        f"  approved             {approved or 0:>6}",
        f"  new leases signed    {leases:>6}   {rate(leases, leads)}",
        "  (renewals excluded from the lease count)",
    ])


@tool
def lead_sources(property_name: str, period: str) -> str:
    """Where one property's leads came from — channel and lead type."""
    with closing(open_ro()) as con:
        try:
            pid, name = resolve_property(con, property_name)
            first, last = window(period)
        except ValueError as exc:
            return str(exc)
        by_channel = con.execute("""
            SELECT ch.name AS channel, l.lead_type AS kind, COUNT(*) AS n
            FROM leads l JOIN channels ch ON ch.channel_id = l.channel_id
            WHERE l.property_id = ? AND date(l.created_at) BETWEEN ? AND ?
            GROUP BY ch.channel_id, l.lead_type
            ORDER BY n DESC
        """, (pid, first, last)).fetchall()

    if not by_channel:
        return f"no leads at {name} between {first} and {last}"
    total = sum(r["n"] for r in by_channel)
    lines = [f"Lead sources — {name}, {first} to {last} ({total} leads)"]
    for r in by_channel:
        lines.append(f"  {r['channel']:<24} {r['kind']:<10} {r['n']:>5}"
                     f"  {r['n'] / total * 100:>5.1f}%")
    return "\n".join(lines)


@tool
def property_list() -> str:
    """Every property we manage, with its market and unit count."""
    with closing(open_ro()) as con:
        rows = con.execute("SELECT name, market, total_units, asset_class "
                           "FROM properties ORDER BY market, name").fetchall()
    return "\n".join(f"{r['name']} — {r['market']}, class {r['asset_class']}, "
                     f"{r['total_units']} units" for r in rows)


SYSTEM = """You are Digible's funnel analyst. When an owner asks "so what is actually
happening at this property", you walk them down the funnel one stage at a time.

New leases only — renewals are excluded, because no marketing dollar acquired one.
Point at the stage with the worst conversion rather than reciting every number.

Always use your tools; never estimate a number yourself.
The data covers 14 properties, January through June 2026. If someone asks for a
month outside that, say so rather than guessing.
Be concise and lead with the number."""

TOOLS = [funnel, lead_sources, property_list]


async def main() -> int:
    # ─── plumbing ───────────────────────────────────────────────────────────
    # Free text, and nothing else. No --property, no --month, no defaults:
    # wiring an example value into argparse would mean the *caller* did the
    # interpreting. No arguments opens a chat; a question answers once.
    ap = argparse.ArgumentParser(description="Single-property funnel.")
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
    return await repl.chat(agent, title="Digible — Property Funnel", hints=["show me the funnel for Legacy Trails in May",
               "where are its leads coming from?",
               "now do Harborview 900 for the same month"])


if __name__ == "__main__":
    raise SystemExit(repl.run(main()))
