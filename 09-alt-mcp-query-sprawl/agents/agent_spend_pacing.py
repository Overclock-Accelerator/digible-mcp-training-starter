#!/usr/bin/env python3
"""Spend Pacing — are we spending at the rate the budgets imply?

    python agent_spend_pacing.py
    python agent_spend_pacing.py "which properties are pacing over budget in May?"

DATA ACCESS STYLE: raw SQL, inline, against one module-level connection opened
at import. It is the shortest path from "I need a number" to a number, which is
why so much code looks like this.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from langchain_core.tools import tool

from _prelude import COMMON_RULES, arg_parser, create_agent, repl, require, run

DB = Path(__file__).resolve().parent.parent / "digible.db"
if not DB.exists():
    raise SystemExit(f"error: {DB} not found")

CON = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
CON.row_factory = sqlite3.Row

# All-in cost: media plus every Digible fee, because that is what the owner is
# invoiced. Every agent in this folder uses the same basis.
ALL_IN = "(s.media_spend + s.mgmt_fee + s.service_fee)"

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


def to_month(text: str) -> str:
    """'May' / 'may 2026' / '2026-05' / '5/2026' -> '2026-05'."""
    raw = (text or "").strip().lower()
    m = re.search(r"(20\d\d)[-/](\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})[-/](20\d\d)", raw)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    year = (re.search(r"(20\d\d)", raw) or [None, "2026"])[1]
    for i, name in enumerate(MONTHS, start=1):
        if raw.startswith(name[:3]) or name in raw:
            return f"{year}-{i:02d}"
    raise ValueError(f"could not read a month out of {text!r}")


def month_span(month: str) -> tuple[str, str]:
    """Inclusive (first_day, last_day) for a 'YYYY-MM'."""
    row = CON.execute(
        "SELECT ?||'-01', date(?||'-01','start of month','+1 month','-1 day')",
        (month, month)).fetchone()
    return row[0], row[1]


@tool
def properties(market: str = "") -> str:
    """List the properties we manage, optionally filtered to one market.

    Use this to turn a half-remembered name into the exact one, or to find out
    what is in a market like 'Denver' or 'Tampa'.
    """
    sql = "SELECT name, market, total_units FROM properties"
    params: list = []
    if market:
        sql += " WHERE market LIKE ?"
        params.append(f"%{market}%")
    sql += " ORDER BY market, name"
    rows = CON.execute(sql, params).fetchall()
    if not rows:
        return f"no properties matching market {market!r}"
    return "\n".join(f"{r['name']} — {r['market']}, {r['total_units']} units"
                     for r in rows)


@tool
def pacing(month: str, property_name: str = "") -> str:
    """Budget vs actual spend for a month, by property.

    month: anything month-ish — 'May', '2026-05', 'may 2026'.
    property_name: optional exact property name to narrow to one.

    `monthly_budget` is a MEDIA budget, so pace compares it against media spend.
    Pace over 110% is overspending; under 90% is underspending. The invoiced
    column adds Digible's management and service fees on top — that is what the
    owner actually pays, and it is normally well above the media budget.
    """
    try:
        month = to_month(month)
    except ValueError as exc:
        return str(exc)
    first, last = month_span(month)

    sql = f"""
        SELECT p.name                                   AS property,
               SUM({ALL_IN})                            AS actual,
               SUM(s.media_spend)                       AS media
        FROM spend_daily s
        JOIN properties p ON p.property_id = s.property_id
        WHERE s.spend_date >= ? AND s.spend_date <= ?
    """
    params: list = [first, last]
    if property_name:
        sql += " AND p.name = ?"
        params.append(property_name)
    sql += " GROUP BY p.property_id ORDER BY p.name"
    actuals = {r["property"]: r for r in CON.execute(sql, params).fetchall()}

    bsql = """
        SELECT p.name AS property, SUM(c.monthly_budget) AS budget
        FROM campaigns c
        JOIN properties p ON p.property_id = c.property_id
        WHERE c.start_date <= ? AND (c.end_date IS NULL OR c.end_date >= ?)
    """
    bparams: list = [last, first]
    if property_name:
        bsql += " AND p.name = ?"
        bparams.append(property_name)
    bsql += " GROUP BY p.property_id"
    budgets = {r["property"]: r["budget"]
               for r in CON.execute(bsql, bparams).fetchall()}

    if not actuals:
        return f"no spend recorded for {month}" + (
            f" at {property_name}" if property_name else "")

    lines = [f"Budget pacing — {month}",
             "  media pace = media spend / media budget; invoiced = media + Digible fees",
             f"  {'property':<28}{'budget':>11}{'media':>11}{'pace':>8}"
             f"{'invoiced':>12}{'of budget':>11}  status"]
    for name, row in actuals.items():
        budget = budgets.get(name) or 0.0
        pace = (row["media"] / budget * 100) if budget else 0.0
        invoiced_pct = (row["actual"] / budget * 100) if budget else 0.0
        flag = "OVER" if pace > 110 else "under" if pace < 90 else "on pace"
        lines.append(
            f"  {name:<28}{'$' + format(budget, ',.0f'):>11}"
            f"{'$' + format(row['media'], ',.0f'):>11}{pace:>7.1f}%"
            f"{'$' + format(row['actual'], ',.0f'):>12}{invoiced_pct:>10.1f}%  {flag}")
    return "\n".join(lines)


@tool
def pacing_by_campaign(month: str, property_name: str) -> str:
    """Break one property's month down to campaign level.

    Shows the media budget, the media spent against it, the pace, and what the
    owner was invoiced once Digible's fees are added. SEO and organic social
    are flat service subscriptions: they carry a fee and no media at all.
    """
    try:
        month = to_month(month)
    except ValueError as exc:
        return str(exc)
    first, last = month_span(month)

    rows = CON.execute(f"""
        SELECT ch.name                    AS channel,
               c.name                     AS campaign,
               c.monthly_budget           AS budget,
               SUM(s.media_spend)         AS media,
               SUM({ALL_IN})              AS actual
        FROM spend_daily s
        JOIN campaigns   c  ON c.campaign_id = s.campaign_id
        JOIN channels    ch ON ch.channel_id = s.channel_id
        JOIN properties  p  ON p.property_id = s.property_id
        WHERE s.spend_date >= ? AND s.spend_date <= ? AND p.name = ?
        GROUP BY c.campaign_id
        ORDER BY ch.name
    """, (first, last, property_name)).fetchall()

    if not rows:
        return f"no campaigns with spend for {property_name} in {month}"
    lines = [f"{property_name} — {month}",
             f"  {'channel':<24}{'budget':>10}{'media':>10}{'pace':>8}{'invoiced':>11}"]
    for r in rows:
        pace = (r["media"] / r["budget"] * 100) if r["budget"] else 0.0
        note = "   (service fee only — no media)" if not r["media"] else ""
        lines.append(f"  {r['channel']:<24}{'$' + format(r['budget'], ',.0f'):>10}"
                     f"{'$' + format(r['media'], ',.0f'):>10}{pace:>7.1f}%"
                     f"{'$' + format(r['actual'], ',.0f'):>11}{note}")
    return "\n".join(lines)


SYSTEM = """You are Digible's spend pacing analyst. Account managers ask you whether
the money is going out at the rate the budgets say it should.

A campaign's monthly_budget is a MEDIA budget, so pace is media spend against it.
Flag anything pacing above 110% or below 90%. Separately, always say what the
owner was INVOICED — media plus Digible's management and service fees — because
that number is normally 20-40% above the media budget and it is the one on the
statement. Do not confuse the two.
""" + COMMON_RULES

TOOLS = [properties, pacing, pacing_by_campaign]


async def main() -> int:
    args = arg_parser("Budget pacing analysis.").parse_args()
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
    return await repl.chat(agent, title="Digible — Spend Pacing", hints=["which properties are pacing over budget in May?",
               "break Legacy Trails down by campaign for May",
               "what about the Denver properties in June?"])


if __name__ == "__main__":
    raise SystemExit(run(main()))
