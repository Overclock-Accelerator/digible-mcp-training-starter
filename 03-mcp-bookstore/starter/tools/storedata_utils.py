"""
Shared helpers for working with `storedata.json`.

Why this file exists
--------------------
When building LangChain tools, it's easy to accidentally duplicate low-level concerns
like: "Where is the JSON file?" "How do we parse types reliably?" "How do we format prices?"

So we keep those details here, and let each tool focus on *decision logic*.

What this file provides
-----------------------
- `load_store_books()`: reads and caches the list of raw book dicts from `storedata.json`
- `BookView`: a typed, normalized view of one book record
- `book_view(...)`: converts raw JSON dict -> `BookView`
- `effective_price(...)`: sale price if on sale, else base price
- `norm(...)`: normalization helper for rough string matching
- `fmt_money(...)`: display helper for prices
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    # Tools live in `tools/`, so the repo root is one directory above this file.
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_store_books() -> list[dict[str, Any]]:
    """
    Load the inventory from `storedata.json`.

    The `@lru_cache(maxsize=1)` means:
    - We only read/parse the JSON file once per Python process.
    - Tools can call `load_store_books()` freely without worrying about I/O cost.
    """
    path = _project_root() / "storedata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    books = data.get("books", [])
    if not isinstance(books, list):
        return []
    return [b for b in books if isinstance(b, dict)]


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def norm(s: str) -> str:
    """
    Normalize text for *rough matching*.

    This is not NLP; it's just:
    - lowercase
    - replace non-alphanumeric characters with spaces
    - collapse runs of punctuation into a single separator
    """
    return _NON_ALNUM_RE.sub(" ", s.lower()).strip()


def fmt_money(value: Any) -> str | None:
    """
    Format a number as a USD string like `$12.99`.

    Returns None if the input can't be converted to a float.
    """
    try:
        return f"${float(value):.2f}"
    except Exception:
        return None


@dataclass(frozen=True)
class BookView:
    """
    Typed "view" of a book record.

    The JSON inventory may contain missing keys or values stored as strings.
    Converting to this dataclass lets the rest of the codebase be simpler
    (e.g., `b.pages` is an `int | None` rather than "maybe a string").
    """
    id: int | None
    title: str
    author: str
    genre: str
    rating: float | None
    pages: int | None
    price: float | None
    year: int | None
    description: str
    review_count: int | None
    on_sale: bool
    sale_price: float | None
    discount_percent: int | None
    is_featured: bool


def book_view(book: dict[str, Any]) -> BookView:
    """
    Convert a raw JSON dict into a `BookView`.

    Tools generally do:
    - `raw_books = load_store_books()`
    - `books = [book_view(b) for b in raw_books]`
    so the rest of their logic is type-stable.
    """
    def _to_int(x: Any) -> int | None:
        try:
            return int(x)
        except Exception:
            return None

    def _to_float(x: Any) -> float | None:
        try:
            return float(x)
        except Exception:
            return None

    return BookView(
        id=_to_int(book.get("id")),
        title=str(book.get("title", "")).strip(),
        author=str(book.get("author", "")).strip(),
        genre=str(book.get("genre", "")).strip(),
        rating=_to_float(book.get("rating")),
        pages=_to_int(book.get("pages")),
        price=_to_float(book.get("price")),
        year=_to_int(book.get("year")),
        description=str(book.get("description", "")).strip(),
        review_count=_to_int(book.get("reviewCount")),
        on_sale=bool(book.get("onSale", False)),
        sale_price=_to_float(book.get("salePrice")),
        discount_percent=_to_int(book.get("discountPercent")),
        is_featured=bool(book.get("isFeatured", False)),
    )


def effective_price(b: BookView) -> float | None:
    """
    Return the price the customer would pay *today*.

    - If the book is on sale and a `sale_price` is present, use it.
    - Otherwise fall back to the base `price`.
    """
    if b.on_sale and b.sale_price is not None:
        return b.sale_price
    return b.price

