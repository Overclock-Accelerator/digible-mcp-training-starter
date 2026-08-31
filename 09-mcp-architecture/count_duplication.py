#!/usr/bin/env python3
"""Measure the duplication in agents/. No API key, no network, no model.

    python count_duplication.py
    python count_duplication.py --detail      # name every implementation

Six agents answer six different questions. To do it, each of them had to solve
the same handful of small problems: find the database, turn "May" into a pair
of dates, turn a half-remembered property name into the exact one, add up
spend, count leads, count calls, format a number.

This script counts how many times each of those was solved independently, and
how many lines it took. It reads the files with `ast` and classifies each
function by what it actually touches, so the number moves if you edit the code.

The number it prints is the whole exercise. `10-mcp-architecture-solved`
prints the same number after the six agents were rewritten against one server.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parent / "agents"

# What counts as a shared primitive, and how to spot one in a function body.
# Deliberately literal: these match the tables and idioms actually in the files.
PRIMITIVES: list[tuple[str, str]] = [
    ("open the database",   r"sqlite3\.connect|digible\.db"),
    # These match a function that DOES the work, not one that calls a helper —
    # month-name tables and date arithmetic, or a query against `properties`.
    ("resolve a period",    r"\bjan\b|january|MONTH_WORDS|LAST_DAY|monthrange|"
                            r"calendar\.month|start of month|'%m'|\+1 month|"
                            r"date\(year|month_shift|_end_of"),
    ("look up a property",  r"FROM properties|properties ORDER BY|"
                            r"load\(\"properties\"\)"),
    ("fetch spend",         r"spend_daily"),
    ("fetch leads",         r"FROM leads|load\(\"leads\"\)|leads_by_channel"),
    ("fetch calls",         r"FROM calls"),
    ("fetch tours",         r"FROM tours|load\(\"tours\"\)"),
    ("fetch leases",        r"FROM leases"),
    ("fetch applications",  r"FROM applications"),
    ("format numbers",      r":[,>\d.]*,[.\d]*f\}|\.rjust\(|\.ljust\(|f\"\$"),
]


def source_of(node: ast.AST, text: str) -> str:
    return ast.get_source_segment(text, node) or ""


def is_tool(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(getattr(d, "id", getattr(d, "attr", None)) == "tool"
               for d in node.decorator_list)


# A line is data access if it does one of these things. Counting per LINE, not
# per function, is what stops a file that inlines its SQL inside a @tool from
# looking cleaner than one that pulled the same SQL into a helper.
LINE_RULES = re.compile(
    r"\b(SELECT|FROM|JOIN|WHERE|GROUP\s+BY|ORDER\s+BY|BETWEEN|COUNT\(|SUM\(|"
    r"AVG\(|ROUND\(|strftime|sqlite3|row_factory|fetchall|fetchone|execute)\b|"
    r"digible\.db|month|период|:[,>\d.]*,[.\d]*f\}|\.rjust\(|\.ljust\(",
    re.IGNORECASE)


def plumbing_lines(lines: list[str]) -> set[int]:
    """1-based line numbers inside a `# ─── plumbing ───` … `end plumbing` block.

    Every agent carries the same bootstrap inline — shared/ onto sys.path, the
    key out of .env.local, argparse — so each file reads top to bottom without
    a helper module. It is neither data access nor tools, it is byte-identical
    in all six, and counting it would move the number without anything about
    the duplication having changed. So it is fenced off in the source and
    skipped here.
    """
    inside: set[int] = set()
    open_at: int | None = None
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("# ─── plumbing"):
            open_at = i
        elif stripped.startswith("# ─── end plumbing") and open_at is not None:
            inside.update(range(open_at, i + 1))
            open_at = None
    return inside


def sql_string_lines(text: str) -> set[int]:
    """1-based line numbers inside a triple-quoted string that contains SELECT."""
    inside: set[int] = set()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "SELECT" in node.value.upper() and node.end_lineno > node.lineno:
                inside.update(range(node.lineno, node.end_lineno + 1))
        if isinstance(node, ast.JoinedStr) and node.end_lineno > node.lineno:
            raw = ast.get_source_segment(text, node) or ""
            if "SELECT" in raw.upper():
                inside.update(range(node.lineno, node.end_lineno + 1))
    return inside


def scan(path: Path) -> dict:
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines()

    # Docstrings are prose, not code: exclude them from every count.
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body:
                first = node.body[0]
                doc_lines.update(range(first.lineno, first.end_lineno + 1))

    sql_lines = sql_string_lines(text)
    plumbing = plumbing_lines(lines)
    code = [i for i, l in enumerate(lines, start=1)
            if l.strip() and not l.strip().startswith("#")
            and i not in doc_lines and i not in plumbing]
    data = [i for i in code
            if i in sql_lines or LINE_RULES.search(lines[i - 1])]

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            src = source_of(node, text)
            if node.lineno in plumbing:
                continue                      # bootstrap, not this file's work
            hits = [name for name, pattern in PRIMITIVES
                    if re.search(pattern, src, re.IGNORECASE)]
            functions.append({
                "name": node.name,
                "lines": len([l for l in src.splitlines() if l.strip()]),
                "primitives": hits,
                "tool": is_tool(node),
            })

    return {"path": path, "total": len(code), "data_lines": len(data),
            "plumbing_lines": len([i for i in plumbing
                                   if lines[i - 1].strip()
                                   and not lines[i - 1].strip().startswith("#")]),
            "functions": functions,
            "tool_lines": sum(f["lines"] for f in functions if f["tool"])}


def label(path: Path) -> str:
    """A short name for a file: the agent it belongs to."""
    if path.name == "_spendlib.py":
        return "channel efficiency (helper)"
    return path.stem.replace("agent_", "").replace("_", " ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detail", action="store_true",
                    help="list every function implementing every primitive")
    args = ap.parse_args()

    files = sorted(AGENTS.glob("*.py"))
    if not files:
        raise SystemExit(f"no agent files found in {AGENTS}")
    reports = [scan(p) for p in files]

    print("\nDATA ACCESS PER FILE")
    print("  Blank lines, comments and docstrings excluded throughout.")
    print("  So is the fenced `# --- plumbing ---` bootstrap each agent carries:")
    print("  identical in all six, neither data access nor tools.")
    print("  " + "-" * 72)
    print(f"  {'file':<34}{'lines':>8}{'data access':>14}{'tools':>9}{'share':>8}")
    for r in reports:
        share = r["data_lines"] / r["total"] * 100 if r["total"] else 0
        print(f"  {label(r['path']):<34}{r['total']:>8}{r['data_lines']:>14}"
              f"{r['tool_lines']:>9}{share:>7.0f}%")
    print("  " + "-" * 72)
    totals = (sum(r["total"] for r in reports),
              sum(r["data_lines"] for r in reports),
              sum(r["tool_lines"] for r in reports))
    print(f"  {'TOTAL':<34}{totals[0]:>8}{totals[1]:>14}{totals[2]:>9}"
          f"{totals[1] / totals[0] * 100:>7.0f}%")

    print("\nSHARED PRIMITIVES, SOLVED SEPARATELY")
    print("  Independent implementations of the same small problem.")
    print("  " + "-" * 72)
    print(f"  {'primitive':<26}{'files':>7}{'impls':>7}   solved separately in")
    for name, _ in PRIMITIVES:
        impls = [(r, f) for r in reports for f in r["functions"]
                 if name in f["primitives"]]
        if not impls:
            continue
        owners = sorted({label(r["path"]) for r, _ in impls})
        print(f"  {name:<26}{len(owners):>7}{len(impls):>7}   "
              f"{', '.join(owners)}")
        if args.detail:
            for r, f in impls:
                kind = "@tool" if f["tool"] else "helper"
                print(f"      {r['path'].name}:{f['name']}  "
                      f"({f['lines']} lines, {kind})")
    print("  " + "-" * 72)

    repeated = [n for n, _ in PRIMITIVES
                if len({r["path"] for r in reports for f in r["functions"]
                        if n in f["primitives"]}) > 1]
    print(f"\n  {len(repeated)} primitives are implemented in more than one file.")
    plumbing = sum(r["plumbing_lines"] for r in reports)
    print(f"  {plumbing:,} further lines are the identical per-file plumbing "
          f"block, counted nowhere.")
    print(f"  {totals[1]:,} of {totals[0]:,} lines across the six agents "
          f"and their one helper module ({totals[1] / totals[0] * 100:.0f}%) "
          f"are data access.")
    print("  Every one of those lines is a place a definition can drift.\n")
    print("  Now go read the six files and answer the question in README.md:")
    print("  what is the SMALLEST set of tools that serves all six agents?\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
