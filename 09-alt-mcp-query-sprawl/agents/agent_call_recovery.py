#!/usr/bin/env python3
"""Call Recovery — where are we losing phone calls, and what did they cost?

    python agent_call_recovery.py
    python agent_call_recovery.py "which properties are missing the most calls in June?"

DATA ACCESS STYLE: its own presentation layer. Somebody got tired of tables that
did not line up and wrote a column-aware renderer, a currency formatter and a
percentage formatter — and then had to write the queries that feed them. The
renderer is genuinely nicer than the string concatenation in the other five
files. It is also a sixth copy of money formatting and a sixth copy of "spend
for a property and a month".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.tools import tool

from _prelude import COMMON_RULES, arg_parser, create_agent, repl, require, run

DB = str(Path(__file__).resolve().parent.parent / "digible.db")


# --- this file's presentation layer ------------------------------------------

def money(value: float | None) -> str:
    return "—" if value is None else f"${value:,.0f}"


def pct(part: float, whole: float, places: int = 1) -> str:
    return "—" if not whole else f"{part / whole * 100:.{places}f}%"


def table(headers: list[str], rows: list[list[str]], title: str = "") -> str:
    """Left-align text columns, right-align anything that looks numeric."""
    if not rows:
        return title or "(no rows)"
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows))
              for i, h in enumerate(headers)]
    numeric = [all(str(r[i]).lstrip("$-+").replace(",", "").replace(".", "")
                   .rstrip("%").isdigit() or str(r[i]) == "—" for r in rows)
               for i in range(len(headers))]

    def line(cells: list) -> str:
        return "  " + "  ".join(
            str(c).rjust(widths[i]) if numeric[i] else str(c).ljust(widths[i])
            for i, c in enumerate(cells))

    out = ([title] if title else []) + [line(headers)]
    out.append("  " + "  ".join("-" * w for w in widths))
    out.extend(line(r) for r in rows)
    return "\n".join(out)


# --- and this file's data access ---------------------------------------------

def fetch(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def month_range(month: str) -> tuple[str, str]:
    """Inclusive bounds for a month, resolved by SQLite's own date maths."""
    text = (month or "").strip().lower()
    stems = "jan feb mar apr may jun jul aug sep oct nov dec".split()
    year, num = "2026", None
    for token in text.replace("-", " ").replace("/", " ").split():
        if token.isdigit() and len(token) == 4:
            year = token
        elif token.isdigit():
            num = int(token)
        elif token[:3] in stems:
            num = stems.index(token[:3]) + 1
    if num is None:
        raise ValueError(f"could not read a month out of {month!r}")
    first = f"{year}-{num:02d}-01"
    last = fetch("SELECT date(?, 'start of month','+1 month','-1 day')",
                 (first,))[0][0]
    return first, last


def known_properties() -> list[str]:
    return [r[0] for r in fetch("SELECT name FROM properties ORDER BY name")]


def exact_property(text: str) -> str:
    needle = (text or "").strip().lower()
    names = known_properties()
    for name in names:
        if name.lower() == needle:
            return name
    hits = [n for n in names if needle and needle in n.lower()]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"no single property matches {text!r}. "
                     f"Known: {', '.join(names)}")


# --- tools --------------------------------------------------------------------

@tool
def missed_calls(month: str, property_name: str = "") -> str:
    """Answered vs missed calls per property for a month.

    FionaCalls labels every call 'Lead', 'Missed Call' or 'Not a Lead'.
    A missed call at a property with vacancy is lost revenue, not a metric.
    """
    try:
        first, last = month_range(month)
        clause, params = "", []
        if property_name:
            clause, params = " AND p.name = ?", [exact_property(property_name)]
    except ValueError as exc:
        return str(exc)

    rows = fetch(f"""
        SELECT p.name                                    AS property,
               COUNT(*)                                  AS total,
               SUM(c.answered)                           AS answered,
               SUM(c.fiona_label = 'Missed Call')        AS missed,
               SUM(c.fiona_label = 'Lead')               AS lead_calls
        FROM calls c
        JOIN properties p ON p.property_id = c.property_id
        WHERE date(c.started_at) BETWEEN ? AND ?{clause}
        GROUP BY p.property_id
        ORDER BY missed DESC
    """, (first, last, *params))

    if not rows:
        return f"no calls recorded between {first} and {last}"
    body = [[r["property"], f"{r['total']:,}", f"{r['answered']:,}",
             f"{r['missed']:,}", pct(r["missed"], r["total"]),
             f"{r['lead_calls']:,}"] for r in rows]
    return table(["property", "calls", "answered", "missed", "miss rate", "leads"],
                 body, title=f"Calls — {first[:7]}")


@tool
def missed_calls_by_channel(month: str, property_name: str = "") -> str:
    """Missed calls by channel, next to what we spent on that channel.

    The spend column is all-in — media plus Digible's management and service
    fees — so a channel with high spend and a high miss rate is money going into
    a phone nobody answers.
    """
    try:
        first, last = month_range(month)
        clause, params = "", []
        if property_name:
            clause, params = " AND p.name = ?", [exact_property(property_name)]
    except ValueError as exc:
        return str(exc)

    calls = fetch(f"""
        SELECT ch.name AS channel, COUNT(*) AS total,
               SUM(c.fiona_label = 'Missed Call') AS missed
        FROM calls c
        JOIN channels   ch ON ch.channel_id = c.channel_id
        JOIN properties p  ON p.property_id = c.property_id
        WHERE date(c.started_at) BETWEEN ? AND ?{clause}
        GROUP BY ch.channel_id
    """, (first, last, *params))

    spend = {r["channel"]: r["cost"] for r in fetch(f"""
        SELECT ch.name AS channel,
               SUM(s.media_spend + s.mgmt_fee + s.service_fee) AS cost
        FROM spend_daily s
        JOIN channels   ch ON ch.channel_id = s.channel_id
        JOIN properties p  ON p.property_id = s.property_id
        WHERE s.spend_date BETWEEN ? AND ?{clause}
        GROUP BY ch.channel_id
    """, (first, last, *params))}

    if not calls:
        return f"no calls between {first} and {last}"
    body = [[r["channel"], f"{r['total']:,}", f"{r['missed']:,}",
             pct(r["missed"], r["total"]), money(spend.get(r["channel"]))]
            for r in sorted(calls, key=lambda r: -r["missed"])]
    scope = property_name or "portfolio"
    return table(["channel", "calls", "missed", "miss rate", "all-in spend"],
                 body, title=f"Missed calls by channel — {scope}, {first[:7]}")


@tool
def call_hours(month: str, property_name: str = "") -> str:
    """Miss rate by hour of day — the shape of a staffing problem."""
    try:
        first, last = month_range(month)
        clause, params = "", []
        if property_name:
            clause, params = " AND p.name = ?", [exact_property(property_name)]
    except ValueError as exc:
        return str(exc)

    rows = fetch(f"""
        SELECT CAST(strftime('%H', c.started_at) AS INTEGER) AS hour,
               COUNT(*) AS total,
               SUM(c.fiona_label = 'Missed Call') AS missed
        FROM calls c
        JOIN properties p ON p.property_id = c.property_id
        WHERE date(c.started_at) BETWEEN ? AND ?{clause}
        GROUP BY hour ORDER BY hour
    """, (first, last, *params))

    if not rows:
        return f"no calls between {first} and {last}"
    body = [[f"{r['hour']:02d}:00", f"{r['total']:,}", f"{r['missed']:,}",
             pct(r["missed"], r["total"])] for r in rows]
    return table(["hour", "calls", "missed", "miss rate"], body,
                 title=f"Calls by hour — {property_name or 'portfolio'}, {first[:7]}")


SYSTEM = """You are Digible's call recovery analyst. A missed call at a property with
vacancy is a lost lease, so you treat the miss rate as money rather than a metric.

FionaCalls labels every call 'Lead', 'Missed Call' or 'Not a Lead'.
Spend figures are ALL-IN — media plus Digible's management and service fees.
Lead with the worst offender and say what it is costing.
""" + COMMON_RULES

TOOLS = [missed_calls, missed_calls_by_channel, call_hours]


async def main() -> int:
    args = arg_parser("Missed call analysis.").parse_args()
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
    return await repl.chat(agent, title="Digible — Call Recovery", hints=["which properties are missing the most calls in June?",
               "which channel are we wasting the most spend on?",
               "what time of day are we missing them?"])


if __name__ == "__main__":
    raise SystemExit(run(main()))
