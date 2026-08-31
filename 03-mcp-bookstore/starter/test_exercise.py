"""The specification for `bookstore_server.py`. This file is the exercise.

    python test_exercise.py               # the whole contract
    python test_exercise.py -c A          # one checkpoint at a time
    python test_exercise.py -v            # show the failure detail in full

Read it as a contract, not as a hint sheet. It says what your server must
expose and what shape the answers must have; it says nothing about how to get
there, because that is the part worth doing yourself. Build until it passes —
whether you type the code or prompt an agent into typing it, this is what you
are aiming at.

No pytest, no API key, no network. It talks to YOUR bookstore_server.py through
FastMCP's in-memory client, which is the same code path the HTTP and stdio
transports use minus the process boundary — so a pass here means the server is
genuinely working, not just importable. Once it passes, run the server for real
in one terminal and an agent in another; that is where the rest of the lesson
is.

Every test runs against a throwaway copy of storedata.json, so the write
checkpoints can never damage the catalog you are working from.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Point the server at a scratch catalog BEFORE importing it — inventory.py
# resolves its data path at import time.
_TMP = Path(tempfile.mkdtemp(prefix="bookstore-test-"))
shutil.copy(HERE / "storedata.json", _TMP / "storedata.json")
os.environ["BOOKSTORE_DATA"] = str(_TMP / "storedata.json")
os.environ["BOOKSTORE_ADMIN_TOKEN"] = "test-admin-token"
sys.path.insert(0, str(HERE))

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    GREEN = RED = DIM = RESET = ""

# A Windows console defaults to cp1252, which cannot encode U+2713/U+2717 --
# every failure line would die with UnicodeEncodeError before showing you the
# checkpoint it failed. Ask for UTF-8, and fall back to ASCII marks if the
# stream will not take it. This is a test runner: it must survive the console
# it is run in.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
try:
    "✓✗".encode(sys.stdout.encoding or "utf-8")
    TICK, CROSS = "✓", "✗"
except (UnicodeEncodeError, LookupError):
    TICK, CROSS = "PASS", "FAIL"

CHECKPOINTS = {
    "A": "one read tool behind an MCP server",
    "B": "the rest of the read tools, returning structured data",
    "C": "write tools that actually persist",
    "D": "writes the model cannot authorize itself",
}

# Printed when a checkpoint fails. The contract, in full: the tools that must
# exist, the parameter names this file will call them with, and the shape of
# what must come back. How you satisfy it is yours.
SPEC = {
    "A": """\
    search_books(agent_name, title, author, genre, keyword, min_price,
                 max_price, min_rating, max_pages, min_year, max_year,
                 on_sale_only, limit) -> dict
      · agent_name is required; every filter is optional and independently
        typed. No parameter takes a customer's sentence.
      · returns {"count": int, "books": [book, ...]}, each book a dict with at
        least genre, price, effective_price.
      · applied filters actually filter.""",
    "B": """\
    get_book(agent_name, title) -> dict
      · one book, every field it holds. Fails loudly when the store does not
        stock the title — a failed call, not a sentence saying "sorry".
    recommend_books(agent_name, genres, max_price, count, ...) -> dict
      · returns {"count", "books"}, exactly `count` books, each structured.
      · takes several typed preferences, not one blob of English.
    build_bundle(agent_name, budget, ...) -> dict
      · returns {"budget", "books", "count", "total", "remaining"}.
      · total never exceeds budget, and it fits as many books in as it can.""",
    "C": """\
    add_book(agent_name, title, author, genre, price, pages, year,
             rating, description) -> dict   # the stored book, with an id
    update_book(agent_name, title, price, on_sale, sale_price, ...) -> dict
      · only the fields passed are changed; effective_price tracks the sale.
    delete_book(agent_name, title) -> dict
      · Every write must reach disk AND be visible to the very next read in
        the same process. If those two disagree, the disagreement is the
        lesson — go and look at how inventory.py loads the catalog.""",
    "D": """\
    The write tools must require an admin credential, and:
      · that credential must NOT appear in any tool's input schema. A value
        the model can see is a value the model can invent.
      · with no credential, a write is refused AND changes nothing.
      · with one, the identical call succeeds.
      · this file presents the credential in BOOKSTORE_ADMIN_TOKEN, because it
        drives your server in-process where there is no request to read a
        header off. Over HTTP the credential arrives in a header instead, so
        the write path must accept either.""",
}


class Failure(Exception):
    """A checkpoint expectation that did not hold."""


def check(condition: object, message: str) -> None:
    if not condition:
        raise Failure(message)


async def tools_for(client) -> dict:
    return {t.name: t for t in await client.list_tools()}


def require_tool(tools: dict, name: str, checkpoint: str) -> None:
    check(
        name in tools,
        f"checkpoint {checkpoint} requires a tool named {name!r}, and the server "
        f"does not expose one.\n"
        f"    Exposed right now: {', '.join(sorted(tools)) or '(nothing)'}",
    )


# --------------------------------------------------------------------------
# Checkpoint A — one read tool, behind the protocol
# --------------------------------------------------------------------------

async def checkpoint_a(client) -> None:
    tools = await tools_for(client)
    require_tool(tools, "search_books", "A")

    schema = tools["search_books"].inputSchema.get("properties", {})
    check("agent_name" in schema,
          "search_books has no `agent_name` parameter. Every tool in this course "
          "takes one — see ../README.md.")

    result = await client.call_tool("search_books", {
        "agent_name": "test", "genre": "Science Fiction", "max_price": 20.0, "limit": 5,
    })
    data = result.data
    check(isinstance(data, dict),
          f"search_books returned {type(data).__name__}, not a dict. MCP tools should "
          "return structured data, not prose — that is the whole point of the refactor.")
    check("books" in data and isinstance(data["books"], list),
          f"search_books' result has no `books` list. Got keys: {sorted(data)}")
    check(data["books"], "search_books found no Science Fiction under $20. There are "
                         "several in storedata.json, so a filter is being applied too strictly.")
    for b in data["books"]:
        check(isinstance(b, dict), f"each book should be a dict, got {type(b).__name__}")
        check(b.get("genre") == "Science Fiction",
              f"{b.get('title')!r} is {b.get('genre')!r}, not Science Fiction — the "
              "genre filter is not being applied")
        price = b.get("effective_price", b.get("price"))
        check(price is not None and price <= 20.0,
              f"{b.get('title')!r} costs {price}, over the $20 max_price")


# --------------------------------------------------------------------------
# Checkpoint B — the rest of the reads, structured
# --------------------------------------------------------------------------

async def checkpoint_b(client) -> None:
    tools = await tools_for(client)
    for name in ("get_book", "recommend_books", "build_bundle"):
        require_tool(tools, name, "B")

    book = (await client.call_tool("get_book", {
        "agent_name": "test", "title": "The Midnight Library",
    })).data
    check(isinstance(book, dict),
          f"get_book returned {type(book).__name__}, not a dict. If it is still "
          "returning butler prose, the refactor is not done — the host model writes "
          "the prose now.")
    check(book.get("author") == "Matt Haig",
          f"get_book('The Midnight Library') gave author {book.get('author')!r}")
    check(book.get("price") == 16.99, f"expected price 16.99, got {book.get('price')!r}")

    try:
        await client.call_tool("get_book", {"agent_name": "test", "title": "Zzyzx Nonexistent"})
        raise Failure("get_book on a title the store does not stock should raise a "
                      "ToolError, not return a not-found string. Errors are a protocol "
                      "concept here, not a sentence for the model to parse.")
    except Failure:
        raise
    except Exception:
        pass

    recs = (await client.call_tool("recommend_books", {
        "agent_name": "test", "genres": ["Science Fiction"], "max_price": 25.0, "count": 3,
    })).data
    check(isinstance(recs, dict) and isinstance(recs.get("books"), list),
          f"recommend_books should return a dict with a `books` list, got {recs!r:.120}")
    check(len(recs["books"]) == 3, f"asked for 3 recommendations, got {len(recs['books'])}")
    check(all(isinstance(b, dict) for b in recs["books"]),
          "each recommendation should be a structured book, not a formatted string")

    schema = tools["recommend_books"].inputSchema.get("properties", {})
    check(len(schema) >= 3,
          f"recommend_books takes only {sorted(schema)}. If it still takes one "
          "natural-language blob, the regex NLU is still in there — let the host "
          "model parse the request and pass you typed parameters.")

    bundle = (await client.call_tool("build_bundle", {
        "agent_name": "test", "budget": 65.0,
    })).data
    check(isinstance(bundle, dict), "build_bundle should return a dict")
    check(bundle.get("books"), "build_bundle found nothing to buy with $65")
    total = bundle.get("total")
    check(total is not None and total <= 65.0,
          f"the bundle totals {total}, over the $65 budget")
    check(len(bundle["books"]) >= 4,
          f"$65 should buy more than {len(bundle['books'])} book(s) — the knapsack is "
          "maximizing the wrong thing")


# --------------------------------------------------------------------------
# Checkpoint C — writes that persist AND are visible
# --------------------------------------------------------------------------

TEST_TITLE = "A Checkpoint C Test Book"


async def checkpoint_c(client) -> None:
    tools = await tools_for(client)
    for name in ("add_book", "update_book", "delete_book"):
        require_tool(tools, name, "C")

    before = (await client.call_tool("search_books", {"agent_name": "test", "limit": 500})).data
    added = (await client.call_tool("add_book", {
        "agent_name": "test", "title": TEST_TITLE, "author": "A Tester",
        "genre": "Fiction", "price": 12.50, "pages": 200, "year": 2026,
    })).data
    check(isinstance(added, dict) and added.get("title") == TEST_TITLE,
          f"add_book should return the stored book, got {added!r:.120}")
    check(added.get("id") is not None, "the new book has no id")

    found = (await client.call_tool("search_books", {
        "agent_name": "test", "title": TEST_TITLE,
    })).data
    check(found["books"], (
        "add_book saved the book, but searching for it right afterwards finds "
        "nothing.\n"
        "    The write reached the disk — go and look at storedata.json, it is in "
        "there.\n"
        "    So why can the read not see it? Look at how the catalog is loaded in "
        "inventory.py.\n"
        "    (This bug is inherited from the original repo, and it is harmless "
        "there. Ask yourself what changed.)"
    ))
    check(found["books"][0]["price"] == 12.50,
          f"the stored price is {found['books'][0]['price']}, not 12.50")

    updated = (await client.call_tool("update_book", {
        "agent_name": "test", "title": TEST_TITLE, "on_sale": True, "sale_price": 8.00,
    })).data
    check(updated.get("on_sale") is True, "update_book did not set on_sale")
    reread = (await client.call_tool("get_book", {"agent_name": "test", "title": TEST_TITLE})).data
    check(reread.get("sale_price") == 8.00,
          f"after update, sale_price reads back as {reread.get('sale_price')!r}")
    check(reread.get("effective_price") == 8.00,
          "a book on sale should report the sale price as its effective_price — "
          "otherwise every price the customer is quoted is wrong")

    await client.call_tool("delete_book", {"agent_name": "test", "title": TEST_TITLE})
    after = (await client.call_tool("search_books", {"agent_name": "test", "limit": 500})).data
    check(len(after["books"]) == len(before["books"]),
          f"catalog went from {len(before['books'])} to {len(after['books'])} books; "
          "delete_book did not clean up after the test")


# --------------------------------------------------------------------------
# Checkpoint D — the credential the model cannot reach
# --------------------------------------------------------------------------

async def checkpoint_d(client) -> None:
    tools = await tools_for(client)
    require_tool(tools, "add_book", "D")

    props = tools["add_book"].inputSchema.get("properties", {})
    for leak in ("admin", "token", "admin_token", "credential", "api_key"):
        check(leak not in props, (
            f"add_book's schema exposes a {leak!r} parameter, so the model can see it "
            "— and a credential the model can see is a credential the model can "
            "invent. The credential must reach the tool without ever appearing in "
            "the schema the model is given."
        ))

    saved = os.environ.pop("BOOKSTORE_ADMIN_TOKEN", None)
    try:
        try:
            await client.call_tool("add_book", {
                "agent_name": "impostor", "title": "Unauthorized Book",
                "author": "Nobody", "genre": "Fiction", "price": 1.00,
            })
            raise Failure(
                "add_book succeeded with no admin credential presented. The write "
                "path must refuse when no credential reaches it, and it must refuse "
                "before it touches the catalog."
            )
        except Failure:
            raise
        except Exception:
            pass

        listing = (await client.call_tool("search_books", {
            "agent_name": "test", "title": "Unauthorized Book",
        })).data
        check(not listing["books"],
              "the refused write still changed the catalog — check the order of the "
              "authorization check and the save")
    finally:
        if saved is not None:
            os.environ["BOOKSTORE_ADMIN_TOKEN"] = saved

    ok = (await client.call_tool("add_book", {
        "agent_name": "test", "title": "Authorized Book", "author": "An Admin",
        "genre": "Fiction", "price": 1.00,
    })).data
    check(ok.get("title") == "Authorized Book",
          "with the credential present, the same call should succeed")
    try:
        await client.call_tool("delete_book", {"agent_name": "test", "title": "Authorized Book"})
    except Exception as exc:
        raise Failure(
            f"the authorized write succeeded but the catalog cannot see it afterwards "
            f"({exc}). That is checkpoint C's bug, not an authorization problem — fix C first."
        ) from exc


TESTS = {"A": checkpoint_a, "B": checkpoint_b, "C": checkpoint_c, "D": checkpoint_d}


async def run(selected: list[str], verbose: bool) -> int:
    try:
        from fastmcp import Client
        import bookstore_server
    except Exception as exc:
        print(f"{RED}{CROSS}{RESET} could not import bookstore_server.py: {exc}")
        if verbose:
            traceback.print_exc()
        print(f"\n{DIM}Fix the import before anything else — checkpoint A starts with a "
              f"server that at least loads.{RESET}")
        return 1

    failures = 0
    for name in selected:
        print(f"\n{name} — {CHECKPOINTS[name]}")
        try:
            async with Client(bookstore_server.mcp) as client:
                await TESTS[name](client)
        except Failure as exc:
            failures += 1
            print(f"  {RED}{CROSS} {exc}{RESET}")
            print(f"\n{DIM}  Checkpoint {name} requires:{RESET}\n{DIM}{SPEC[name]}{RESET}")
        except Exception as exc:
            failures += 1
            print(f"  {RED}{CROSS} {type(exc).__name__}: {exc}{RESET}")
            if verbose:
                traceback.print_exc()
            print(f"\n{DIM}  Checkpoint {name} requires:{RESET}\n{DIM}{SPEC[name]}{RESET}")
        else:
            print(f"  {GREEN}{TICK} passed{RESET}")

    print()
    if failures:
        print(f"{RED}{failures} of {len(selected)} checkpoint(s) failing.{RESET} "
              f"{DIM}Work them in order — later ones build on earlier ones.{RESET}")
    else:
        print(f"{GREEN}All {len(selected)} checkpoint(s) passing.{RESET}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check your bookstore MCP server.")
    parser.add_argument("-c", "--checkpoint", action="append", choices=sorted(CHECKPOINTS),
                        help="run only this checkpoint (repeatable)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show tracebacks")
    args = parser.parse_args()
    selected = sorted(set(args.checkpoint)) if args.checkpoint else sorted(CHECKPOINTS)
    try:
        return asyncio.run(run(selected, args.verbose))
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
