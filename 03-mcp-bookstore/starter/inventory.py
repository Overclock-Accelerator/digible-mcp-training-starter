"""The bookstore's data layer — loading, normalizing, searching, bundling.

GIVEN TO YOU, COMPLETE. You should not need to change much in here, and the
exercise is not about rewriting a knapsack solver.

This is the part of LangBookStore worth keeping: the decision logic behind
`tools/recommend_books.py` and `tools/budget_bundler.py`, lifted out and given
typed parameters instead of a natural-language blob. Compare `search()` below
with the ~200 lines of `_extract_*` regex in `tools/recommend_books.py` — that
is what the host model makes unnecessary.

Nothing in here imports fastmcp. Your server is a thin seam on top.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# BOOKSTORE_DATA lets the tests point at a scratch copy instead of the shipped
# catalog. Without it, write tools would edit the file this folder ships with.
DATA_PATH = Path(os.environ.get("BOOKSTORE_DATA") or (HERE / "storedata.json"))

# The catalog's 26 genres, spelled exactly as they appear in storedata.json.
# Enumerated in the search/recommend docstrings so the model never has to guess
# at a spelling — "vague descriptions" is the top cause of bad tool calls.
GENRES = (
    "Adventure", "Biography", "Business", "Classic", "Dystopian", "Fantasy",
    "Fiction", "Finance", "Health", "Historical Fiction", "History",
    "Literary Fiction", "Mystery", "Nature", "Nonfiction", "Philosophy",
    "Politics", "Post-Apocalyptic", "Psychology", "Romance", "Science Fiction",
    "Self-Help", "Spirituality", "Thriller", "Western", "Young Adult",
)


# --------------------------------------------------------------------------
# Loading. Cached, exactly as the original repo cached it.
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_raw() -> tuple[dict[str, Any], ...]:
    """Read and parse storedata.json.

    `@lru_cache(maxsize=1)` means the file is read and parsed once per process,
    so tools can call this as often as they like without paying for the I/O.
    """
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    books = data.get("books", [])
    if not isinstance(books, list):
        return ()
    return tuple(b for b in books if isinstance(b, dict))


def load_books() -> list[dict[str, Any]]:
    """Every book in the catalog, normalized to snake_case."""
    return [book_view(b) for b in _load_raw()]


def save_books(books: list[dict[str, Any]]) -> None:
    """Write the catalog back to disk."""
    payload = {"books": [to_record(b) for b in books]}
    tmp = DATA_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA_PATH)  # atomic-ish: a crash mid-write can't truncate the catalog


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def norm(s: str) -> str:
    """Lowercase, punctuation-to-space. For rough matching, not NLP."""
    return _NON_ALNUM_RE.sub(" ", str(s).lower()).strip()


def _to_int(x: Any) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def book_view(raw: dict[str, Any]) -> dict[str, Any]:
    """Raw catalog record -> a normalized dict safe to hand back over MCP.

    A plain dict is what the wire wants: FastMCP serializes it straight into
    `structuredContent`, and the model reads typed fields instead of parsing
    prose.
    """
    price = _to_float(raw.get("price"))
    sale_price = _to_float(raw.get("salePrice"))
    on_sale = bool(raw.get("onSale", False))
    return {
        "id": _to_int(raw.get("id")),
        "title": str(raw.get("title", "")).strip(),
        "author": str(raw.get("author", "")).strip(),
        "genre": str(raw.get("genre", "")).strip(),
        "rating": _to_float(raw.get("rating")),
        "pages": _to_int(raw.get("pages")),
        "price": price,
        "year": _to_int(raw.get("year")),
        "description": str(raw.get("description", "")).strip(),
        "review_count": _to_int(raw.get("reviewCount")),
        "on_sale": on_sale,
        "sale_price": sale_price,
        "discount_percent": _to_int(raw.get("discountPercent")),
        "is_featured": bool(raw.get("isFeatured", False)),
        # Precomputed so the model never has to work out whether the sale applies.
        "effective_price": sale_price if (on_sale and sale_price is not None) else price,
    }


def to_record(book: dict[str, Any]) -> dict[str, Any]:
    """A normalized book -> the camelCase shape storedata.json uses on disk."""
    record: dict[str, Any] = {
        "id": book.get("id"),
        "title": book.get("title", ""),
        "author": book.get("author", ""),
        "genre": book.get("genre", ""),
        "rating": book.get("rating"),
        "pages": book.get("pages"),
        "price": book.get("price"),
        "year": book.get("year"),
        "description": book.get("description", ""),
        "reviewCount": book.get("review_count"),
        "onSale": bool(book.get("on_sale", False)),
        "isFeatured": bool(book.get("is_featured", False)),
    }
    if record["onSale"]:
        record["salePrice"] = book.get("sale_price")
        record["discountPercent"] = book.get("discount_percent")
    return record


def effective_price(book: dict[str, Any]) -> float | None:
    """What the customer pays today."""
    return book.get("effective_price")


# --------------------------------------------------------------------------
# Lookup and search
# --------------------------------------------------------------------------

def find_by_title(title: str, books: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Find one book by title: exact normalized match first, then substring.

    `tools/get_answers.py` scanned the *whole user question* for any title that
    appeared inside it, longest-wins. That heuristic exists only because the
    tool was handed a sentence. Give it a title parameter and it is a lookup.
    """
    books = load_books() if books is None else books
    want = norm(title)
    if not want:
        return None
    for b in books:
        if norm(b["title"]) == want:
            return b
    candidates = [b for b in books if want in norm(b["title"]) or norm(b["title"]) in want]
    if not candidates:
        return None
    # Longest title wins — it is the most specific match.
    return max(candidates, key=lambda b: len(norm(b["title"])))


def match_genre(value: str) -> str | None:
    """Map a loose genre string onto one of the catalog's 26 genres.

    'sci-fi' -> 'Science Fiction'. Kept deliberately small: the model is told
    the exact genre list in the tool docstring, so this only has to absorb the
    handful of aliases a customer might type verbatim.
    """
    v = norm(value)
    if not v:
        return None
    aliases = {
        "sci fi": "Science Fiction", "scifi": "Science Fiction",
        "ya": "Young Adult", "self help": "Self-Help",
        "post apocalyptic": "Post-Apocalyptic", "biz": "Business",
        "non fiction": "Nonfiction", "true crime": "Mystery",
    }
    if v in aliases:
        return aliases[v]
    for g in GENRES:
        if norm(g) == v:
            return g
    for g in GENRES:
        if v in norm(g) or norm(g) in v:
            return g
    return None


def search(
    *,
    title: str | None = None,
    author: str | None = None,
    genre: str | None = None,
    keyword: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    max_pages: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    on_sale_only: bool = False,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Hard-filter the catalog on typed constraints, best-rated first.

    Every parameter is optional and every one that is supplied is enforced.
    No parameter means "no opinion", which is why there is no regex anywhere
    in this function: nothing has to be guessed from a sentence.
    """
    genre_match = match_genre(genre) if genre else None
    kw = norm(keyword) if keyword else None
    out: list[dict[str, Any]] = []

    for b in load_books():
        price = b["effective_price"]
        if title and norm(title) not in norm(b["title"]):
            continue
        if author and norm(author) not in norm(b["author"]):
            continue
        if genre_match and b["genre"] != genre_match:
            continue
        if kw and kw not in norm(f"{b['title']} {b['author']} {b['genre']} {b['description']}"):
            continue
        if on_sale_only and not b["on_sale"]:
            continue
        if min_price is not None and (price is None or price < min_price):
            continue
        if max_price is not None and (price is None or price > max_price):
            continue
        if min_rating is not None and (b["rating"] is None or b["rating"] < min_rating):
            continue
        if max_pages is not None and (b["pages"] is None or b["pages"] > max_pages):
            continue
        if min_year is not None and (b["year"] is None or b["year"] < min_year):
            continue
        if max_year is not None and (b["year"] is None or b["year"] > max_year):
            continue
        out.append(b)

    out.sort(key=lambda b: (-(b["rating"] or 0), -(b["review_count"] or 0), b["title"]))
    return out[: max(1, limit)]


# --------------------------------------------------------------------------
# Recommendation scoring — ported from tools/recommend_books.py.
#
# Same weights as the original. What is gone is the ~200 lines of `_extract_*`
# regex that used to produce these preferences from a sentence.
# --------------------------------------------------------------------------

def _median(nums: list[int]) -> int:
    return sorted(nums)[len(nums) // 2] if nums else 0


def score_book(
    book: dict[str, Any],
    *,
    genres: tuple[str, ...],
    authors: tuple[str, ...],
    keywords: tuple[str, ...],
    on_sale: bool | None,
    max_price: float | None,
    min_rating: float | None,
    popularity: str | None,
    median_reviews: int,
) -> tuple[float, list[str]]:
    """Score one book against typed preferences. Higher is better."""
    score = 0.0
    reasons: list[str] = []
    text = norm(f"{book['title']} {book['author']} {book['genre']} {book['description']}")
    genre_n = norm(book["genre"])

    if authors:
        if any(norm(a) == norm(book["author"]) for a in authors):
            score += 6.0
            reasons.append("matches your author")
        else:
            score -= 1.5

    if genres:
        if any(norm(g) in genre_n for g in genres):
            score += 6.0
            reasons.append("fits your genre")
        elif any(norm(g) in text for g in genres):
            score += 3.0
            reasons.append("fits the vibe you're after")
        else:
            score -= 2.0

    hits = sum(1 for kw in keywords if kw and norm(kw) in text)
    if hits:
        score += min(4.0, float(hits))
        reasons.append("lines up with your keywords")

    if on_sale is True and book["on_sale"]:
        score += 2.0
        reasons.append("on sale")
    elif on_sale is True and not book["on_sale"]:
        score -= 3.0

    price = book["effective_price"]
    if max_price is not None:
        if price is None or price > max_price:
            score -= 5.0
        else:
            score += 2.0
            reasons.append("within budget")

    if book["rating"] is not None:
        score += (book["rating"] - 3.5) * 2.0
        if book["rating"] >= 4.4:
            reasons.append("very well rated")
    if min_rating is not None and (book["rating"] is None or book["rating"] < min_rating):
        score -= 5.0

    rc = book["review_count"]
    if popularity == "high" and rc is not None and median_reviews:
        score += 2.0 if rc >= median_reviews else -2.0
    elif popularity == "low" and rc is not None and median_reviews:
        score += 2.0 if rc < median_reviews else -2.0
        if rc < median_reviews:
            reasons.append("a quieter pick")

    if book["is_featured"]:
        score += 0.5

    return score, reasons


def recommend(
    *,
    genres: tuple[str, ...] = (),
    authors: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    on_sale: bool | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    popularity: str | None = None,
    count: int = 3,
) -> list[dict[str, Any]]:
    """Rank the catalog against typed preferences and return the top `count`."""
    books = load_books()
    if not books:
        return []
    median_reviews = _median([b["review_count"] for b in books if b["review_count"] is not None])

    scored = []
    for b in books:
        score, reasons = score_book(
            b, genres=genres, authors=authors, keywords=keywords, on_sale=on_sale,
            max_price=max_price, min_rating=min_rating, popularity=popularity,
            median_reviews=median_reviews,
        )
        scored.append((score, b, reasons))

    scored.sort(key=lambda t: (-t[0], -(t[1]["rating"] or 0), t[1]["title"]))
    return [
        {**b, "score": round(score, 2), "reasons": reasons}
        for score, b, reasons in scored[: max(1, count)]
    ]


# --------------------------------------------------------------------------
# Budget bundling — 0/1 knapsack, ported from tools/budget_bundler.py.
#
# Objective: maximize (book count, then total spend) under the budget, with
# optional required-genre coverage. Untouched by the move to MCP.
# --------------------------------------------------------------------------

def _price_cents(book: dict[str, Any]) -> int | None:
    p = book["effective_price"]
    return None if p is None else int(round(float(p) * 100))


def _bundle_candidates(
    books: list[dict[str, Any]],
    *,
    genres: tuple[str, ...],
    on_sale: bool | None,
    min_year: int | None,
    max_year: int | None,
    min_rating: float | None,
    max_pages: int | None,
) -> list[dict[str, Any]]:
    wanted = {norm(g) for g in genres}
    out = []
    for b in books:
        if wanted and norm(b["genre"]) not in wanted:
            continue
        if on_sale is True and not b["on_sale"]:
            continue
        if on_sale is False and b["on_sale"]:
            continue
        if min_year is not None and (b["year"] is None or b["year"] < min_year):
            continue
        if max_year is not None and (b["year"] is None or b["year"] > max_year):
            continue
        if min_rating is not None and (b["rating"] is None or b["rating"] < min_rating):
            continue
        if max_pages is not None and (b["pages"] is None or b["pages"] > max_pages):
            continue
        if _price_cents(b) is None:
            continue
        out.append(b)
    return out


def solve_bundle(
    candidates: list[dict[str, Any]],
    *,
    budget_cents: int,
    required_genres: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """0/1 knapsack with optional required-genre coverage.

    dp[mask][cents] holds the best (count, spend) reachable having covered
    `mask` of the required genres for exactly `cents` of spend. Maximize book
    count first, then spend, so an equal-count bundle that uses more of the
    budget wins.
    """
    genre_to_bit = {norm(g): (1 << i) for i, g in enumerate(required_genres)}
    full_mask = (1 << len(required_genres)) - 1

    items: list[tuple[int, int, dict[str, Any]]] = []
    for b in candidates:
        pc = _price_cents(b)
        if pc is None or pc <= 0 or pc > budget_cents:
            continue
        items.append((pc, genre_to_bit.get(norm(b["genre"]), 0), b))

    dp: list[list[tuple[int, int, int, int, int] | None]] = [
        [None] * (budget_cents + 1) for _ in range(max(1, 1 << len(required_genres)))
    ]
    dp[0][0] = (0, 0, -1, -1, -1)

    def better(a, b) -> bool:
        return a[0] > b[0] if a[0] != b[0] else a[1] > b[1]

    for idx, (pc, m, _) in enumerate(items):
        for mask in range(len(dp) - 1, -1, -1):
            for c in range(budget_cents - pc, -1, -1):
                cur = dp[mask][c]
                if cur is None:
                    continue
                cand = (cur[0] + 1, c + pc, mask, c, idx)
                existing = dp[mask | m][c + pc]
                if existing is None or better(cand, existing):
                    dp[mask | m][c + pc] = cand

    best_state = None
    best_mask = 0
    search_masks = [full_mask] if full_mask else [0]
    for tm in search_masks:
        for c in range(budget_cents + 1):
            st = dp[tm][c]
            if st is not None and (best_state is None or better(st, best_state)):
                best_state, best_mask = st, tm

    if best_state is None and full_mask:  # couldn't cover every genre; take the best we can
        for tm in range(len(dp)):
            for c in range(budget_cents + 1):
                st = dp[tm][c]
                if st is not None and (best_state is None or better(st, best_state)):
                    best_state, best_mask = st, tm

    if best_state is None:
        return []

    picked: list[dict[str, Any]] = []
    st, mask, c = best_state, best_mask, best_state[1]
    while st is not None and st[4] != -1:
        _, _, prev_mask, prev_c, item_idx = st
        picked.append(items[item_idx][2])
        mask, c = prev_mask, prev_c
        st = dp[mask][c]
    picked.reverse()
    return picked


def build_bundle(
    *,
    budget: float,
    genres: tuple[str, ...] = (),
    require_one_of_each_genre: bool = False,
    on_sale: bool | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    min_rating: float | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Fill a budget with as many qualifying books as possible."""
    budget_cents = int(round(float(budget) * 100))
    resolved = tuple(g for g in (match_genre(g) for g in genres) if g)
    candidates = _bundle_candidates(
        load_books(), genres=resolved, on_sale=on_sale, min_year=min_year,
        max_year=max_year, min_rating=min_rating, max_pages=max_pages,
    )
    required = resolved if (require_one_of_each_genre and len(resolved) >= 2) else ()
    picked = solve_bundle(candidates, budget_cents=budget_cents, required_genres=required)
    total = sum(_price_cents(b) or 0 for b in picked) / 100.0
    return {
        "budget": round(budget, 2),
        "books": picked,
        "count": len(picked),
        "total": round(total, 2),
        "remaining": round(budget - total, 2),
        "genres_requested": list(resolved),
        "candidates_considered": len(candidates),
    }
