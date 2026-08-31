"""A conversational loop for the agents in this repo.

Every example is a conversation, not a one-shot command. That is deliberate:
passing `--letters VALIDTY --center V` proves nothing, because the *caller*
did the thinking. Typing "what's today's bee? VALIDTY, V in the middle" makes
the agent interpret intent and choose the tool itself -- and lets you ask for
three puzzles in a row without restarting anything.

One-shot flags still work for tests, samples and benchmarks. The rule is:
arguments given -> run once and exit; no arguments -> open the conversation.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Awaitable, Callable

from toolvis import show_tools

PROMPT = "\nyou › "
EXITS = {"exit", "quit", ":q", "q"}


def _final_text(message) -> str:
    """Pull the assistant's text out, whatever shape the provider returned.

    Anthropic returns a list of typed content blocks when extended thinking is
    involved; other providers return a plain string. Handle both.
    """
    text = getattr(message, "text", None)
    if isinstance(text, str) and text:
        return text
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "".join(parts)


def banner(title: str, hints: list[str]) -> None:
    print(f"\n{title}")
    print("─" * max(46, len(title)))
    for hint in hints:
        print(f"  {hint}")
    print("  exit / quit / Ctrl-D to leave")


def one_shot(args, *names: str) -> bool:
    """True when the caller supplied enough on the command line to skip the chat.

    Used so `--letters VALIDTY --center V` still answers once and exits (tests,
    samples, benchmarks) while a bare invocation opens the conversation.
    """
    return all(getattr(args, n, None) for n in names)


async def chat(
    agent,
    *,
    title: str,
    hints: list[str],
    system: str | None = None,
    show: bool = True,
) -> int:
    """Run a multi-turn conversation against `agent`.

    History carries across turns, so follow-ups like "now do the same for
    LAMPYRD" work without repeating context.
    """
    banner(title, hints)
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})

    while True:
        try:
            line = input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in EXITS:
            return 0

        messages.append({"role": "user", "content": line})
        seen = len(messages)
        try:
            result = await agent.ainvoke({"messages": messages})
        except Exception as exc:  # keep the session alive on a bad turn
            print(f"  error: {exc}", file=sys.stderr)
            messages.pop()
            continue

        messages = result["messages"]
        if show:
            show_tools(messages[seen:])
        print(_final_text(messages[-1]))


async def once(agent, question: str, *, show: bool = True) -> str:
    """Single question, single answer -- for samples, tests and benchmarks."""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
    if show:
        show_tools(result["messages"])
    return _final_text(result["messages"][-1])


def run(coro: Awaitable) -> int:
    try:
        return asyncio.run(coro) or 0
    except KeyboardInterrupt:
        print()
        return 130
