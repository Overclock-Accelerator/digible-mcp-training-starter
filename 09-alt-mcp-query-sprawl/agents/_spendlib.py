"""Data helpers for agent_channel_efficiency.

Written for that agent and imported by nothing else. This is the good instinct —
somebody noticed their tool functions were getting long and pulled the queries
into a module. It is still the second implementation of "spend for a property
and a month" in this folder, and there are four more to come.
"""

from __future__ import annotations

import calendar
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "digible.db"

# Media plus every Digible fee — what the owner is invoiced.
ALL_IN_SQL = "(media_spend + mgmt_fee + service_fee)"


@contextmanager
def connect():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def month_window(year: int, month: int) -> tuple[str, str]:
    """Inclusive ISO bounds for a calendar month, computed in Python."""
    last_day = calendar.monthrange(year, month)[1]
    return (date(year, month, 1).isoformat(),
            date(year, month, last_day).isoformat())


def parse_month(text: str) -> tuple[int, int]:
    """Return (year, month) from '2026-05', 'May', 'May 2026'."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("a month is required, e.g. '2026-05' or 'May'")
    cleaned = raw.replace("/", "-").replace(",", " ")
    year, month = 2026, None
    for token in cleaned.replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            year = int(token)
        elif token.isdigit():
            month = int(token)
        else:
            for i, name in enumerate(calendar.month_name):
                if i and name.lower().startswith(token.lower()[:3]):
                    month = i
                    break
    if not month or not 1 <= month <= 12:
        raise ValueError(f"could not read a month out of {raw!r}")
    return year, month


def property_names(con) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT name FROM properties ORDER BY name")]


def match_property(con, text: str) -> str | None:
    """Case-insensitive substring match against the property directory."""
    if not text:
        return None
    needle = text.strip().lower()
    for name in property_names(con):
        if needle == name.lower() or needle in name.lower():
            return name
    raise ValueError(f"no property matching {text!r}. "
                     f"Known: {', '.join(property_names(con))}")


def spend_by_channel(con, start: str, end: str,
                     property_name: str | None = None) -> dict[str, dict]:
    """All-in spend, media, impressions and clicks per channel over a window."""
    sql = f"""
        SELECT ch.name                 AS channel,
               SUM({ALL_IN_SQL})       AS all_in,
               SUM(s.media_spend)      AS media,
               SUM(s.impressions)      AS impressions,
               SUM(s.clicks)           AS clicks
        FROM spend_daily s
        JOIN channels   ch ON ch.channel_id = s.channel_id
        JOIN properties p  ON p.property_id = s.property_id
        WHERE s.spend_date BETWEEN ? AND ?
    """
    params: list = [start, end]
    if property_name:
        sql += " AND p.name = ?"
        params.append(property_name)
    sql += " GROUP BY ch.channel_id"
    return {r["channel"]: dict(r) for r in con.execute(sql, params)}


def leads_by_channel(con, start: str, end: str,
                     property_name: str | None = None) -> dict[str, int]:
    """Lead count per channel over a window, by lead creation date."""
    sql = """
        SELECT ch.name AS channel, COUNT(*) AS leads
        FROM leads l
        JOIN channels   ch ON ch.channel_id = l.channel_id
        JOIN properties p  ON p.property_id = l.property_id
        WHERE date(l.created_at) BETWEEN ? AND ?
    """
    params: list = [start, end]
    if property_name:
        sql += " AND p.name = ?"
        params.append(property_name)
    sql += " GROUP BY ch.channel_id"
    return {r["channel"]: r["leads"] for r in con.execute(sql, params)}


def months_covered(con) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT DISTINCT substr(spend_date,1,7) FROM spend_daily ORDER BY 1")]
