"""Render the training markdown as self-contained HTML pages.

Ahmed demos this repo off a projector, so the docs ship as HTML in the house
style of ``04-mcp-deployment/index.html``. The stylesheet is inlined and no page
references anything external -- every page must open from disk with no network.

    python shared/render_report.py --all
    python shared/render_report.py 07-mcp-for-all-the-tokens/results/report.md
    python shared/render_report.py --list

The ``.md`` files stay the editable source; the ``.html`` files are generated
output and are safe to delete and regenerate at any time.

Deliberately a small converter rather than a markdown dependency: these are our
own files in a known subset (headings, tables, fences, nested lists, block
quotes, rules, bold/italic/code/links). If a source file starts using markdown
this does not handle, extend this module -- do not hand-edit the HTML.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = Path(__file__).resolve().parent / "page_style.css"

# --------------------------------------------------------------------------
# which files convert
# --------------------------------------------------------------------------

# Excluded on purpose: 06-mcp-breakdown/WORKSHEET.md (attendees fill it in by
# hand, so markdown is the right format), and anything vendored under .venv/,
# .git/ or a cloned servers/ tree.
SKIP_NAMES = {"WORKSHEET.md"}
SKIP_DIRS = {".venv", ".git", "node_modules", "servers", "__pycache__"}


def targets() -> list[Path]:
    """Every markdown file that becomes an HTML page, in demo order."""
    found: list[Path] = []
    for src in ROOT.rglob("*.md"):
        rel = src.relative_to(ROOT)
        if set(rel.parts[:-1]) & SKIP_DIRS or rel.name in SKIP_NAMES:
            continue
        found.append(src)
    return sorted(found, key=lambda p: str(p.relative_to(ROOT)))


CONVERTED = None  # populated lazily; the set of sources that get an .html twin


def converted_set() -> set[Path]:
    global CONVERTED
    if CONVERTED is None:
        CONVERTED = set(targets())
    return CONVERTED


# --------------------------------------------------------------------------
# inline markup
# --------------------------------------------------------------------------

_CODE_SLOT = "\x00%d\x00"


def _rewrite_link(href: str, src: Path) -> str:
    """Point ``../03/README.md`` at the .html twin, if that twin will exist."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "//")):
        return href
    path, sep, frag = href.partition("#")
    if not path.endswith(".md"):
        return href
    resolved = (src.parent / path).resolve()
    if resolved in converted_set():
        return path[: -len(".md")] + ".html" + sep + frag
    return href


def _inline(text: str, src: Path) -> str:
    """Inline markup. Code spans are lifted out first so nothing rewrites them."""
    spans: list[str] = []

    def stash(m: re.Match) -> str:
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return _CODE_SLOT % (len(spans) - 1)

    out = re.sub(r"`([^`]+)`", stash, text)
    out = html.escape(out)
    out = re.sub(
        r"\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{html.escape(_rewrite_link(m.group(2), src))}">{m.group(1)}</a>',
        out,
    )
    # non-greedy so **bold with *emphasis* inside** still pairs correctly
    out = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"(?<![\w\\])_([^_\n]+)_(?![\w])", r"<em>\1</em>", out)
    for n, span in enumerate(spans):
        out = out.replace(_CODE_SLOT % n, span)
    return out


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------

ITEM = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")


def _is_table_head(lines: list[str], i: int) -> bool:
    return (
        lines[i].lstrip().startswith("|")
        and i + 1 < len(lines)
        and bool(re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]))
    )


def _split_row(row: str) -> list[str]:
    row = row.strip()
    row = re.sub(r"^\|", "", row)
    row = re.sub(r"\|$", "", row)
    cells, cur, esc, incode = [], "", False, False
    for ch in row:
        if esc:
            cur += ch if ch == "|" else "\\" + ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "`":
            incode = not incode      # a pipe inside `code` is content, not a cell break
            cur += ch
        elif ch == "|" and not incode:
            cells.append(cur)
            cur = ""
        else:
            cur += ch
    cells.append(cur)
    return [c.strip() for c in cells]


def _table(rows: list[str], src: Path) -> str:
    head = _split_row(rows[0])
    body = [_split_row(r) for r in rows[2:]]  # row 1 is the --- separator
    width = len(head)
    out = ['<div class="tw"><table>', "<thead><tr>"]
    out += [f"<th>{_inline(c, src)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        row = (row + [""] * width)[:width]
        out.append("<tr>" + "".join(f"<td>{_inline(c, src)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _dedent(lines: list[str], n: int) -> list[str]:
    return [l[n:] if len(l) - len(l.lstrip()) >= n else l.lstrip() for l in lines]


def _list(lines: list[str], i: int, src: Path) -> tuple[str, int]:
    """Parse one list, recursing into each item's own block content."""
    base = len(lines[i]) - len(lines[i].lstrip())
    ordered = not ITEM.match(lines[i]).group(2) in ("-", "*")
    items: list[str] = []

    while i < len(lines):
        m = ITEM.match(lines[i])
        if not m or len(m.group(1)) != base:
            break
        if (m.group(2) in ("-", "*")) == ordered:  # a different list starts here
            break
        content = [m.group(3)]
        indent = base + len(m.group(2)) + 1
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                # a blank line continues the item only if indented content follows
                nxt = i + 1
                while nxt < len(lines) and not lines[nxt].strip():
                    nxt += 1
                if nxt < len(lines) and len(lines[nxt]) - len(lines[nxt].lstrip()) > base:
                    content.append("")
                    i += 1
                    continue
                break
            here = len(line) - len(line.lstrip())
            if here <= base and ITEM.match(line):
                break
            if here <= base and (HEADING.match(line) or RULE.match(line) or FENCE.match(line)):
                break
            content.append(line)
            i += 1
        items.append(_blocks(_dedent(content, indent), src, tight=True))
        while i < len(lines) and not lines[i].strip():
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and ITEM.match(lines[j]) and len(lines[j]) - len(lines[j].lstrip()) == base:
                i = j
            break

    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>", i


CALLOUT = re.compile(r"^\s*[*_]{0,2}(note|warn|warning|stop|caution|ok|tip)\b", re.I)
CALL_CLASS = {"note": "note", "tip": "note", "warn": "warn", "warning": "warn",
              "stop": "stop", "caution": "stop", "ok": "ok"}


def _blocks(lines: list[str], src: Path, tight: bool = False) -> str:
    """Convert a list of markdown lines to HTML. ``tight`` unwraps a lone <p>."""
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if FENCE.match(line):
            i += 1
            block = []
            while i < len(lines) and not FENCE.match(lines[i]):
                block.append(lines[i])
                i += 1
            body.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            i += 1
            continue

        if _is_table_head(lines, i):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            body.append(_table(rows, src))
            continue

        if m := HEADING.match(line):
            # Only the masthead carries an h1; a second "# " in the body demotes,
            # so heading hierarchy on the page stays h1 > h2 > h3 > h4.
            level = min(max(len(m.group(1)), 2), 4)
            body.append(f"<h{level}>{_inline(m.group(2).rstrip('#').strip(), src)}</h{level}>")
            i += 1
            continue

        if RULE.match(line):
            body.append('<hr class="soft">')
            i += 1
            continue

        if ITEM.match(line):
            chunk, i = _list(lines, i, src)
            body.append(chunk)
            continue

        if line.lstrip().startswith(">"):
            quote = []
            while i < len(lines) and (lines[i].lstrip().startswith(">") or
                                      (quote and lines[i].strip() and not ITEM.match(lines[i])
                                       and not HEADING.match(lines[i]))):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            klass = "note"
            if m := CALLOUT.match(quote[0] if quote else ""):
                klass = CALL_CLASS.get(m.group(1).lower(), "note")
            body.append(f'<div class="call {klass}">' + _blocks(quote, src) + "</div>")
            continue

        para = []
        while i < len(lines) and lines[i].strip():
            if para and (ITEM.match(lines[i]) or HEADING.match(lines[i])
                         or FENCE.match(lines[i]) or RULE.match(lines[i])
                         or lines[i].lstrip().startswith(">")
                         or _is_table_head(lines, i)):
                break
            para.append(lines[i].strip())
            i += 1
        body.append(f"<p>{_inline(' '.join(para), src)}</p>")

    out = "\n".join(body)
    if tight and len(body) == 1 and out.startswith("<p>") and out.endswith("</p>"):
        return out[3:-4]
    return out


# --------------------------------------------------------------------------
# page assembly
# --------------------------------------------------------------------------

TITLE_PREFIX = re.compile(r"^\d+\s*[—–-]\s*")


def masthead(src: Path, h1: str | None) -> tuple[str, str]:
    """(eyebrow, title) wired from the file's own location and its H1."""
    rel = src.relative_to(ROOT)
    parts = rel.parts
    folder = parts[0] if len(parts) > 1 else ""
    num = folder[:2] if re.match(r"^\d\d-", folder) else ""

    if not num:
        eyebrow = "MCP Training"
    elif len(parts) == 2 and rel.name == "README.md":
        eyebrow = f"MCP Training · Part {num}"
    elif "results" in parts:
        eyebrow = f"MCP Training · Part {num} · Results"
    elif "samples" in parts:
        eyebrow = f"MCP Training · Part {num} · Samples"
    else:
        eyebrow = f"MCP Training · Part {num}"

    title = rel.stem
    if h1:
        title = re.sub(r"[*`]", "", h1).strip()
        if TITLE_PREFIX.match(title):
            # "01 — the same solver" -> "The same solver"; the number is already
            # in the eyebrow, and it is taken from the folder, not from the H1.
            title = TITLE_PREFIX.sub("", title)
            title = title[:1].upper() + title[1:]
    return eyebrow, title or rel.stem


def to_html(md: str, src: Path) -> tuple[str, str, str, str]:
    """Return (eyebrow, title, standfirst_html, body_html)."""
    lines = md.splitlines()

    # Lift the H1 into the masthead, and the paragraph under it into the standfirst.
    h1 = None
    start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if m := re.match(r"^#\s+(.*)$", line):
            h1 = m.group(1)
            start = i + 1
        break

    standfirst = ""
    if h1 is not None:
        j = start
        while j < len(lines) and not lines[j].strip():
            j += 1
        para = []
        while j < len(lines) and lines[j].strip():
            if HEADING.match(lines[j]) or ITEM.match(lines[j]) or FENCE.match(lines[j]) \
               or RULE.match(lines[j]) or lines[j].lstrip().startswith((">", "|")):
                para = []
                break
            para.append(lines[j].strip())
            j += 1
        if para:
            standfirst = _inline(" ".join(para), src)
            start = j

    eyebrow, title = masthead(src, h1)
    return eyebrow, title, standfirst, _blocks(lines[start:], src)


def render(src: Path) -> Path:
    eyebrow, title, standfirst, body = to_html(src.read_text(), src)
    rel = src.relative_to(ROOT)
    stand = f'\n  <p class="standfirst">{standfirst}</p>' if standfirst else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
{CSS.read_text()}
</style>
</head>
<body>
<div class="wrap">

<header class="mast">
  <p class="eyebrow">{html.escape(eyebrow)}</p>
  <h1>{_inline(title, src)}</h1>{stand}
  <div class="meta">
    <span>{html.escape(str(rel))}</span>
  </div>
</header>

<section>
{body}
</section>

<footer><p>Generated from <code>{html.escape(str(rel))}</code>, which is the editable source.
Regenerate every page with <code>python shared/render_report.py --all</code>.</p></footer>
</div>
</body>
</html>
"""
    out = src.with_suffix(".html")
    out.write_text(page)
    return out


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--list":
        for src in targets():
            print(src.relative_to(ROOT))
        return 0
    if not argv or argv[0] == "--all":
        srcs = targets()
    else:
        srcs = [Path(a).resolve() for a in argv]
    if not srcs:
        print("nothing to render")
        return 1
    for src in srcs:
        print("rendered", render(src).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
