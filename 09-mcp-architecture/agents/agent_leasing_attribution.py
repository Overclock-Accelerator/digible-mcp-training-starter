#!/usr/bin/env python3
"""Leasing Attribution — which channels actually produce signed leases?

    python agent_leasing_attribution.py
    python agent_leasing_attribution.py "which channels drove the most leases in Q2?"

DATA ACCESS STYLE: its own period grammar. This agent gets asked about quarters
and halves as often as months, so somebody wrote a parser that handles 'Q2',
'first half', 'last month' and a date range — none of which the other five
understand. It is the fifth month parser in this folder and the only one that
knows what a quarter is.
"""

from __future__ import annotations

import re
import sqlite3

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


DBFILE = Path(__file__).resolve().parent.parent / "digible.db"

MONTH_WORDS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _end_of(year: int, month: int) -> str:
    day = 29 if (month == 2 and _leap(year)) else LAST_DAY[month]
    return f"{year:04d}-{month:02d}-{day:02d}"


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    if not DBFILE.exists():
        raise SystemExit(f"error: {DBFILE} not found")
    con = sqlite3.connect(f"file:{DBFILE}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def data_months() -> list[str]:
    return [r[0] for r in query(
        "SELECT DISTINCT substr(spend_date,1,7) FROM spend_daily ORDER BY 1")]


def period_bounds(period: str) -> tuple[str, str, str]:
    """Return (start, end, label). Understands months, quarters, halves, ranges.

    Accepts: '2026-05', 'May', 'Q2', 'Q2 2026', 'first half', 'last month',
    'all', or '2026-02-01 to 2026-04-15'.
    """
    text = (period or "").strip().lower()
    months = data_months()
    if not text or text in {"all", "everything", "ytd", "to date"}:
        return f"{months[0]}-01", _end_of(*map(int, months[-1].split("-"))), "all data"

    year_match = re.search(r"\b(20\d\d)\b", text)
    year = int(year_match.group(1)) if year_match else int(months[-1][:4])

    if "last month" in text or "previous month" in text:
        y, m = map(int, months[-1].split("-"))
        return f"{y:04d}-{m:02d}-01", _end_of(y, m), months[-1]

    quarter = re.search(r"\bq([1-4])\b", text)
    if quarter:
        q = int(quarter.group(1))
        start_month = (q - 1) * 3 + 1
        return (f"{year:04d}-{start_month:02d}-01",
                _end_of(year, start_month + 2), f"Q{q} {year}")

    if "first half" in text or text.startswith("h1"):
        return f"{year:04d}-01-01", _end_of(year, 6), f"H1 {year}"
    if "second half" in text or text.startswith("h2"):
        return f"{year:04d}-07-01", _end_of(year, 12), f"H2 {year}"

    explicit = re.findall(r"(20\d\d-\d\d-\d\d)", text)
    if len(explicit) == 2:
        return explicit[0], explicit[1], f"{explicit[0]} to {explicit[1]}"

    iso = re.search(r"\b(20\d\d)-(\d{1,2})\b", text)
    if iso:
        y, m = int(iso.group(1)), int(iso.group(2))
        return f"{y:04d}-{m:02d}-01", _end_of(y, m), f"{y:04d}-{m:02d}"

    for word, m in MONTH_WORDS.items():
        if word in text:
            return f"{year:04d}-{m:02d}-01", _end_of(year, m), f"{year:04d}-{m:02d}"

    raise ValueError(f"could not read a period out of {period!r}. "
                     f"Try a month, a quarter like 'Q2', or 'all'. "
                     f"Data covers {months[0]} to {months[-1]}.")


def property_clause(property_name: str) -> tuple[str, list]:
    if not property_name:
        return "", []
    names = [r[0] for r in query("SELECT name FROM properties ORDER BY name")]
    exact = next((n for n in names
                  if n.lower() == property_name.strip().lower()), None)
    if not exact:
        hits = [n for n in names if property_name.strip().lower() in n.lower()]
        if len(hits) != 1:
            raise ValueError(f"no single property matches {property_name!r}. "
                             f"Known: {', '.join(names)}")
        exact = hits[0]
    return " AND p.name = ?", [exact]


@tool
def leases_by_channel(period: str, property_name: str = "") -> str:
    """New leases signed in a period, credited to the channel the lead came in on.

    period: 'May', '2026-05', 'Q2', 'first half', 'all'.
    property_name: optional.

    Renewals are excluded — they have no originating lead. Credit goes to the
    channel recorded on the lease's lead.
    """
    try:
        start, end, label = period_bounds(period)
        clause, params = property_clause(property_name)
    except ValueError as exc:
        return str(exc)

    rows = query(f"""
        SELECT ch.name AS channel, COUNT(*) AS leases,
               ROUND(AVG(ls.net_effective_rent), 0) AS avg_ner
        FROM leases ls
        JOIN leads      l  ON l.lead_id = ls.lead_id
        JOIN channels   ch ON ch.channel_id = l.channel_id
        JOIN properties p  ON p.property_id = ls.property_id
        WHERE ls.is_renewal = 0 AND ls.signed_date BETWEEN ? AND ?{clause}
        GROUP BY ch.channel_id
        ORDER BY leases DESC
    """, (start, end, *params))

    if not rows:
        return f"no new leases signed in {label}"
    total = sum(r["leases"] for r in rows)
    scope = property_name or "portfolio"
    lines = [f"New leases by channel — {scope}, {label} ({total} leases)"]
    for r in rows:
        lines.append(f"  {r['channel']:<24} {r['leases']:>4}"
                     f"  {r['leases'] / total * 100:>5.1f}%"
                     f"  avg NER ${r['avg_ner']:,.0f}")
    return "\n".join(lines)


@tool
def cost_per_lease(period: str, property_name: str = "") -> str:
    """All-in marketing cost per new lease, by channel, over a period.

    Cost is media spend plus Digible's management and service fees, matched to
    the same channel and the same window as the leases.
    """
    try:
        start, end, label = period_bounds(period)
        clause, params = property_clause(property_name)
    except ValueError as exc:
        return str(exc)

    spend = {r["channel"]: r["cost"] for r in query(f"""
        SELECT ch.name AS channel,
               SUM(s.media_spend + s.mgmt_fee + s.service_fee) AS cost
        FROM spend_daily s
        JOIN channels   ch ON ch.channel_id = s.channel_id
        JOIN properties p  ON p.property_id = s.property_id
        WHERE s.spend_date BETWEEN ? AND ?{clause}
        GROUP BY ch.channel_id
    """, (start, end, *params))}

    leases = {r["channel"]: r["n"] for r in query(f"""
        SELECT ch.name AS channel, COUNT(*) AS n
        FROM leases ls
        JOIN leads      l  ON l.lead_id = ls.lead_id
        JOIN channels   ch ON ch.channel_id = l.channel_id
        JOIN properties p  ON p.property_id = ls.property_id
        WHERE ls.is_renewal = 0 AND ls.signed_date BETWEEN ? AND ?{clause}
        GROUP BY ch.channel_id
    """, (start, end, *params))}

    if not spend and not leases:
        return f"nothing recorded for {label}"
    scope = property_name or "portfolio"
    lines = [f"Cost per new lease — {scope}, {label} (all-in cost)"]
    for channel in sorted(set(spend) | set(leases),
                          key=lambda c: -(spend.get(c) or 0)):
        cost, n = spend.get(channel, 0.0) or 0.0, leases.get(channel, 0)
        if not cost:
            per = " no spend "        # organic and direct carry no media cost
        elif n:
            per = f"${cost / n:>9,.0f}"
        else:
            per = "        — "        # spend, but nothing signed
        lines.append(f"  {channel:<24} ${cost:>9,.0f}  {n:>3} leases  {per} each")
    return "\n".join(lines)


@tool
def periods_available() -> str:
    """Which months the data actually covers, and the period words this agent takes."""
    months = data_months()
    return (f"Spend data covers {months[0]} through {months[-1]}: "
            f"{', '.join(months)}.\n"
            "Periods you can ask for: a month ('May', '2026-05'), a quarter "
            "('Q1', 'Q2'), a half ('first half'), 'last month', 'all', or an "
            "explicit range '2026-02-01 to 2026-04-15'.")


SYSTEM = """You are Digible's leasing attribution analyst. Owners want to know which
channels are producing signed leases, not clicks.

Renewals never count — no marketing dollar acquired one. Credit goes to the
channel recorded on the lease's originating lead. Cost is always ALL-IN: media
plus Digible's management and service fees.

Always use your tools; never estimate a number yourself.
The data covers 14 properties, January through June 2026. If someone asks for a
month outside that, say so rather than guessing.
Be concise and lead with the number."""

TOOLS = [leases_by_channel, cost_per_lease, periods_available]


async def main() -> int:
    # ─── plumbing ───────────────────────────────────────────────────────────
    # Free text, and nothing else. No --property, no --month, no defaults:
    # wiring an example value into argparse would mean the *caller* did the
    # interpreting. No arguments opens a chat; a question answers once.
    ap = argparse.ArgumentParser(description="Leases by channel, and what each one cost.")
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
    return await repl.chat(agent, title="Digible — Leasing Attribution", hints=["which channels drove the most leases in Q2?",
               "what did a lease cost us on each channel?",
               "same question for Peachtree Row"])


if __name__ == "__main__":
    raise SystemExit(repl.run(main()))
