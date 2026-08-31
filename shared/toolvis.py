"""Print which tools an agent actually invoked.

Every example in this repo shows its tool calls. That visibility is the point:
the argument of the whole course is that moving a tool behind an MCP server
changes the seam and not the call, and you can only see that if the calls are
on screen in both cases.

The renderer reads a LangChain message list, so it works identically whether
the tools were local `@tool` functions or came from an MCP server -- which is
itself the lesson.
"""

from __future__ import annotations

import json
from typing import Any

WIDTH = 66


def _fmt_args(args: dict[str, Any], limit: int = 88) -> str:
    parts = []
    for key, value in (args or {}).items():
        rendered = json.dumps(value, default=str)
        if len(rendered) > 40:
            rendered = rendered[:37] + '..."'
        parts.append(f"{key}={rendered}")
    line = ", ".join(parts)
    return line if len(line) <= limit else line[: limit - 3] + "..."


def _unwrap(raw: Any) -> Any:
    """Strip the MCP content-block envelope, if there is one.

    A local @tool returns a plain dict. The same tool over MCP arrives as
    [{"type": "text", "text": "<json>"}]. Unwrapping both to the same shape
    is what lets 01's two agents print identical traces.
    """
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
        return _unwrap(raw[0]["text"])
    return raw


def _shape(value: Any, depth: int = 0) -> str:
    """Describe a result by its shape, not its first 160 characters.

    A truncated JSON dump tells you almost nothing -- you see the first two
    words and no idea how much came back. Showing the keys, the scalars, and
    the *size* of each collection tells you what the tool returned and what
    it cost to put in the context window.
    """
    if isinstance(value, dict):
        if depth > 0:
            return "{…}"
        parts = [f"{k}: {_shape(v, depth + 1)}" for k, v in list(value.items())[:6]]
        if len(value) > 6:
            parts.append("…")
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return f"[…{len(value)} items]"
    if isinstance(value, str):
        return f'"{value}"' if len(value) <= 24 else f'"{value[:21]}…"'
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    return str(value)


def _preview(raw: Any) -> str:
    """One line: how big the result was, and what shape it had."""
    parsed = _unwrap(raw)
    size = len(raw if isinstance(raw, str) else json.dumps(raw, default=str))
    return f"{size:,} chars · {_shape(parsed)}"


def collect_tool_calls(messages) -> list[dict[str, Any]]:
    """Pair each tool call with the result that came back for it."""
    calls: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for message in messages:
        for call in (getattr(message, "tool_calls", None) or []):
            call_id = call.get("id") or f"{call.get('name')}-{len(order)}"
            calls[call_id] = {"name": call.get("name"), "args": call.get("args") or {},
                              "result": None}
            order.append(call_id)
        call_id = getattr(message, "tool_call_id", None)
        if call_id and call_id in calls:
            calls[call_id]["result"] = getattr(message, "content", "")

    return [calls[c] for c in order]


def show_tools(messages, title: str = "tools invoked") -> list[dict[str, Any]]:
    """Print every tool call and its result. Returns the calls, for tests."""
    calls = collect_tool_calls(messages)

    print(f"\n──── {title} " + "─" * max(0, WIDTH - len(title) - 6))
    if not calls:
        print("  (none — the model answered without calling a tool)")
    for i, call in enumerate(calls, 1):
        print(f"  {i}. {call['name']}({_fmt_args(call['args'])})")
        if call["result"] is not None:
            print(f"     → {_preview(call['result'])}")
    print("─" * WIDTH)
    return calls
