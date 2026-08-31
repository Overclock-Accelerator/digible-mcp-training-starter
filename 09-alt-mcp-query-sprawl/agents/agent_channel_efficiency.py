#!/usr/bin/env python3
"""Channel Efficiency — what does a lead cost us on each channel?

    python agent_channel_efficiency.py
    python agent_channel_efficiency.py "cost per lead by channel in May"

DATA ACCESS STYLE: a small private helper module, `_spendlib.py`, sitting next
to this file and imported by nothing else. The tidiest of the six — and still
its own private copy of spend, leads, property lookup and month parsing.
"""

from __future__ import annotations

from langchain_core.tools import tool

import _spendlib as sl
from _prelude import COMMON_RULES, arg_parser, create_agent, repl, require, run


@tool
def cost_per_lead(month: str, property_name: str = "") -> str:
    """All-in cost per lead, per channel, for one month.

    month: '2026-05', 'May', 'May 2026'.
    property_name: optional; omit for the whole portfolio.

    Channels with spend but no leads are shown so they are not silently dropped.
    """
    with sl.connect() as con:
        try:
            prop = sl.match_property(con, property_name)
            year, mon = sl.parse_month(month)
        except ValueError as exc:
            return str(exc)
        start, end = sl.month_window(year, mon)
        spend = sl.spend_by_channel(con, start, end, prop)
        leads = sl.leads_by_channel(con, start, end, prop)

    if not spend:
        return (f"no spend in {year}-{mon:02d}"
                + (f" at {prop}" if prop else "")
                + f". Months covered: {', '.join(_months())}")

    scope = prop or "portfolio"
    lines = [f"Cost per lead — {scope}, {year}-{mon:02d} (all-in cost)"]
    for channel in sorted(spend, key=lambda c: -spend[c]["all_in"]):
        row = spend[channel]
        n = leads.get(channel, 0)
        cpl = f"${row['all_in'] / n:>8,.2f}" if n else "       — "
        lines.append(f"  {channel:<24} ${row['all_in']:>9,.0f}  "
                     f"{n:>5} leads  {cpl} / lead")
    unattributed = {c: n for c, n in leads.items() if c not in spend}
    if unattributed:
        lines.append("  (channels with leads but no spend this month: "
                     + ", ".join(f"{c} {n}" for c, n in unattributed.items()) + ")")
    return "\n".join(lines)


@tool
def click_efficiency(month: str, property_name: str = "") -> str:
    """Impressions, clicks, CTR and cost per click by channel for one month."""
    with sl.connect() as con:
        try:
            prop = sl.match_property(con, property_name)
            year, mon = sl.parse_month(month)
        except ValueError as exc:
            return str(exc)
        start, end = sl.month_window(year, mon)
        spend = sl.spend_by_channel(con, start, end, prop)

    if not spend:
        return f"no spend in {year}-{mon:02d}" + (f" at {prop}" if prop else "")
    lines = [f"Click efficiency — {prop or 'portfolio'}, {year}-{mon:02d}"]
    for channel, row in sorted(spend.items(), key=lambda kv: -kv[1]["clicks"]):
        imps, clicks = row["impressions"], row["clicks"]
        ctr = f"{clicks / imps * 100:>5.2f}%" if imps else "    — "
        cpc = f"${row['all_in'] / clicks:>6,.2f}" if clicks else "      — "
        lines.append(f"  {channel:<24} {imps:>9,} imp  {clicks:>7,} clk  "
                     f"{ctr} CTR  {cpc} CPC")
    return "\n".join(lines)


@tool
def which_properties(market: str = "") -> str:
    """List properties, optionally filtered by market, so names can be matched."""
    with sl.connect() as con:
        rows = con.execute(
            "SELECT name, market FROM properties ORDER BY market, name").fetchall()
    if market:
        rows = [r for r in rows if market.lower() in r["market"].lower()]
    if not rows:
        return f"no properties in market {market!r}"
    return "\n".join(f"{r['name']} ({r['market']})" for r in rows)


def _months() -> list[str]:
    with sl.connect() as con:
        return sl.months_covered(con)


SYSTEM = """You are Digible's channel efficiency analyst. Media buyers ask you what a
lead costs on each channel so they know where the next dollar should go.

Cost is always ALL-IN — media spend plus Digible's management and service fees.
A channel with spend and no leads is a finding, not a rounding error: say so.
""" + COMMON_RULES

TOOLS = [cost_per_lead, click_efficiency, which_properties]


async def main() -> int:
    args = arg_parser("Cost per lead by channel.").parse_args()
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
    return await repl.chat(agent, title="Digible — Channel Efficiency", hints=["cost per lead by channel in May",
               "same thing but just for Harborview 900",
               "which channel has the best CTR?"])


if __name__ == "__main__":
    raise SystemExit(run(main()))
