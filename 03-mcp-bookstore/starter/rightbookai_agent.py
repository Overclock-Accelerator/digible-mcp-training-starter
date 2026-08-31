"""
RightBookAI (starter "agent")

This repo is intentionally written as a *teachable* first step toward a LangChain agent.

Important vocabulary (LangChain / "agent-y" systems)
---------------------------------------------------
- **Model**: an LLM client (Anthropic, etc.) that can generate text given messages.
- **Tool**: a normal Python function wrapped for LLM/agent use (LangChain's `@tool`).
- **Agent**: typically an LLM that can decide *when* to call tools, observe results, and iterate.
  This repo uses a real LangChain agent (`create_agent`) to choose tools.

How this file is used
---------------------
- It provides a tiny CLI so you can ask questions like:
  - "Do you have The Great Gatsby?"
  - "Recommend 3 post-apocalyptic sci-fi books under $20"
  - "I have a budget of $65; build me a bundle"
- The LangChain agent created via `create_agent` decides which tool(s) to call.
- Each tool reads from `storedata.json` via helpers in `tools/storedata_utils.py`.

Current behavior (two modes)
----------------------------
- `rightbookai_answer(...)`: uses a real agent via `create_agent` (agent controls tool routing).

Prereqs
-------
- Set `ANTHROPIC_API_KEY` (supports loading from `.env.local` / `.env`)
- Optional: set `RIGHTBOOKAI_MODEL` to override the model name
- Install deps:
  `pip install -U langchain langchain-anthropic python-dotenv colorama`
"""

from __future__ import annotations

import os
import sys
import textwrap
from functools import lru_cache
from typing import Final

from langchain.agents import create_agent
from dotenv import load_dotenv

from tools.budget_bundler import budget_bundler
from tools.get_answers import get_answers
from tools.recommend_books import recommend_books


SYSTEM_PROMPT: Final[str] = (
    "You are RightBookAI, a proper British concierge for LangBookstore. "
    "Be polished, warm, and precise. "
    "You help customers navigate our bookstore by answering questions about available books, "
    "making tailored recommendations, and assembling suggested orders within a stated budget and interests. "
    "Ask brief clarifying questions when needed, and present options with clear reasoning and prices when relevant. "
    "\n\n"
    "Tool usage rules (MANDATORY):\n"
    "- You MUST call at least one tool before answering any user message.\n"
    "- For questions about a specific title's details (genre/author/pages/price/year/sale/availability), call GetAnswers.\n"
    "- For 'recommend/suggest/next read/similar to' requests, call RecommendBooks.\n"
    "- For budgets or 'build a bundle', call BudgetBundler.\n"
    "- Do not answer from general knowledge or guess; use the tool output as the source of truth.\n"
    "- If the relevant tool can't find a title, say so and ask a brief clarifying question.\n"
)
MODEL_NAME: Final[str] = "anthropic:claude-sonnet-5"

# All LangChain tools exposed to the agent.
# Note: `tools/storedata_utils.py` is intentionally *not* included because it provides
# helper functions for reading/normalizing inventory; it's not a user-facing tool.
TOOLS: Final[list[object]] = [get_answers, recommend_books, budget_bundler]

def _load_env() -> None:
    """
    Load env vars from local dotenv files.

    Priority:
    - existing process env
    - .env.local
    - .env
    """
    # Don't override already-set environment variables (useful for CI / Docker / shells).
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)

def _content_to_text(content: object) -> str | None:
    """
    Normalize a message `content` into plain text.

    Chat models return content in one of two shapes:
    - a plain string (the simple case)
    - a list of typed content blocks, e.g. `[{"type": "thinking", ...},
      {"type": "text", "text": "..."}]`. Anthropic models use this shape whenever
      extended thinking is involved, so we keep only the `text` blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        if parts:
            return "\n".join(parts).strip()
    return None

def _extract_agent_text(result: object) -> str:
    """
    Extract a human-readable assistant response from `agent.invoke(...)`.

    `create_agent` returns an agent runnable whose output is typically a dict
    containing a `messages` list, but we keep this defensive to avoid tight
    coupling to internal return shapes.
    """
    if isinstance(result, dict):
        msgs = result.get("messages")
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            if isinstance(last, dict):
                text = _content_to_text(last.get("content"))
                if text is not None:
                    return text
            # LangChain message objects often have `.content`
            text = _content_to_text(getattr(last, "content", None))
            if text is not None:
                return text
            return str(last)
        out = result.get("output")
        if isinstance(out, str):
            return out
    # Fallback: stringify whatever we got.
    return str(result)

def _extract_agent_tool_names(result: object) -> list[str]:
    """
    Extract tool names used during the agent run from `agent.invoke(...)` output.

    We look for tool call metadata on AI messages (tool_calls) and tool result messages.
    This is intentionally defensive across LangChain versions / message shapes.
    """
    msgs: list[object] = []
    if isinstance(result, dict):
        raw = result.get("messages")
        if isinstance(raw, list):
            msgs = raw

    used: list[str] = []
    seen: set[str] = set()

    def add(name: object) -> None:
        if not isinstance(name, str):
            return
        n = name.strip()
        if not n or n in seen:
            return
        seen.add(n)
        used.append(n)

    for m in msgs:
        # Dict-style messages (sometimes returned when using JSON-ish messages)
        if isinstance(m, dict):
            # Tool call list on assistant message
            tc = m.get("tool_calls")
            if isinstance(tc, list):
                for call in tc:
                    if isinstance(call, dict):
                        add(call.get("name"))
            # Tool result message may include a name
            if m.get("role") == "tool":
                add(m.get("name"))
            continue

        # Object-style messages (LangChain BaseMessage variants)
        tool_calls = getattr(m, "tool_calls", None)
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if isinstance(call, dict):
                    add(call.get("name"))
                else:
                    add(getattr(call, "name", None))

        # ToolMessage often has `.name`
        add(getattr(m, "name", None))

    return used


@lru_cache(maxsize=1)
def _rightbookai_agent():
    """
    Create and cache the LangChain agent.

    We cache it because:
    - agent construction can be non-trivial (model initialization, tool wiring)
    - the CLI can call it repeatedly in REPL mode
    """
    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Missing ANTHROPIC_API_KEY. Set it in the environment or in .env.local, then re-run.\n"
            "This project uses a LangChain agent (`create_agent`) for tool routing."
        )

    model_name = os.environ.get("RIGHTBOOKAI_MODEL", MODEL_NAME)

    # LangChain's `create_agent` wires a model + tools into an agent loop that can decide
    # when to call which tool. This is the "real agent" path described in the docs.
    #
    # Ref: https://docs.langchain.com/oss/python/langchain/overview
    return create_agent(
        model=model_name,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def rightbookai_answer_via_agent(question: str) -> str:
    """Answer a user question using a LangChain agent created via `create_agent`."""
    agent = _rightbookai_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return _extract_agent_text(result)

def rightbookai_answer_via_agent_with_meta(question: str) -> tuple[list[str], str]:
    """Return (tool_names_used, response_text) for a user question via the agent."""
    agent = _rightbookai_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return _extract_agent_tool_names(result), _extract_agent_text(result)


def rightbookai_answer(question: str) -> str:
    """
    Answer a user question via the LangChain agent.

    The agent (LLM) controls tool selection/routing.
    """
    return rightbookai_answer_via_agent(question)


def _read_question_from_cli(argv: list[str]) -> str:
    if len(argv) > 1:
        return " ".join(argv[1:]).strip()
    # If running interactively, don't block on sys.stdin.read() (which waits for EOF).
    if sys.stdin.isatty():
        return input("Question: ").strip()
    return sys.stdin.read().strip()


def _init_cli_colors() -> tuple[bool, object]:
    """
    Initialize cross-platform ANSI color support (Windows-friendly).

    Returns: (enabled, color_module_or_None)
    """
    # Avoid emitting ANSI escape codes into piped output / logs.
    if not sys.stdout.isatty():
        return False, None
    if os.environ.get("NO_COLOR"):
        return False, None
    try:
        import colorama  # type: ignore

        # Enables ANSI colors in Windows terminals; no-op elsewhere.
        colorama.just_fix_windows_console()
        return True, colorama
    except Exception:
        return False, None


def _format_cli_output(*, question: str, tool_name: str, response: str) -> str:
    colors_enabled, colorama = _init_cli_colors()

    if colors_enabled and colorama is not None:
        Fore = colorama.Fore
        Style = colorama.Style

        def c(s: str, *, fore: str = "", bright: bool = False) -> str:
            return f"{Style.BRIGHT if bright else ''}{fore}{s}{Style.RESET_ALL}"

        title = c("RightBookAI", fore=Fore.CYAN, bright=True)
        q_hdr = c("Question", fore=Fore.YELLOW, bright=True)
        r_hdr = c("Routed to", fore=Fore.MAGENTA, bright=True)
        a_hdr = c("Response", fore=Fore.GREEN, bright=True)
    else:
        title = "RightBookAI"
        q_hdr = "Question"
        r_hdr = "Routed to"
        a_hdr = "Response"

    sep = "-" * 72
    q_body = textwrap.indent(question.strip(), "  ") if question.strip() else "  (empty)"
    r_body = f"  {tool_name}"
    a_body = textwrap.indent(response.rstrip(), "  ") if response.strip() else "  (no response)"

    return "\n".join(
        [
            sep,
            title,
            sep,
            "",
            f"{q_hdr}:",
            q_body,
            "",
            f"{r_hdr}:",
            r_body,
            "",
            f"{a_hdr}:",
            a_body,
            "",
            sep,
        ]
    )


if __name__ == "__main__":
    # Interactive mode (no args, stdin is a TTY): simple REPL loop.
    if len(sys.argv) == 1 and sys.stdin.isatty():
        while True:
            question = _read_question_from_cli(sys.argv)
            if not question or question.lower() in {"exit", "quit"}:
                raise SystemExit(0)
            tools_used, result = rightbookai_answer_via_agent_with_meta(question)
            tool_name = " + ".join(tools_used) if tools_used else "Agent (create_agent; no tool calls detected)"
            print(_format_cli_output(question=question, tool_name=tool_name, response=result))
        raise SystemExit(0)

    # Non-interactive / one-shot mode: args or piped stdin.
    question = _read_question_from_cli(sys.argv)
    if not question:
        raise SystemExit("Provide a question as args or via stdin.")
    tools_used, result = rightbookai_answer_via_agent_with_meta(question)
    tool_name = " + ".join(tools_used) if tools_used else "Agent (create_agent; no tool calls detected)"
    print(_format_cli_output(question=question, tool_name=tool_name, response=result))

