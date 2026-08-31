"""Token, round-trip and tool-selection accounting, read from the API's own numbers.

Nothing here is estimated. Every AI message returned by `create_agent` carries
`usage_metadata` populated straight from the Anthropic API response, so input
and output tokens are the provider's counts, summed across the whole trajectory
— every round-trip, not just the last one. That matters more here than almost
anywhere, because the entire claim of this folder is that the tool block is
re-sent on *each* round-trip.

Same methodology as the MCP-vs-CLI folder in this repo, so the numbers are
directly comparable.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from toolvis import collect_tool_calls  # noqa: E402


@dataclass
class RunMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0            # round-trips to the model
    tool_calls: int = 0
    tool_result_chars: int = 0
    wall_ms: int = 0

    # -- selection ---------------------------------------------------------
    # The ordered list of (tool, owning server) the model actually invoked.
    # `first_tool` is the selection under test; the rest is the recovery story.
    calls: list = field(default_factory=list)
    first_tool: str = ""
    first_server: str = ""
    expected_tool: str = ""
    expected_server: str = ""
    correct: bool = False          # first tool call was the right one
    wrong_server: bool = False     # first tool call went to another vendor
    recovered: bool = False        # wrong first pick, right tool later in the run
    extra_round_trips: int = 0     # round-trips beyond the 2 a clean run takes

    final_text: str = ""
    messages: list = field(default_factory=list, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("messages", None)
        d["total_tokens"] = self.total_tokens
        return d


def collect(messages: list, expected_tool: str, owners: dict[str, str]) -> RunMetrics:
    """Walk an agent trajectory and total up what it cost and what it picked.

    `owners` maps tool name to the server that exposes it, so a wrong pick can
    be classified as "same idea, wrong vendor" rather than just "wrong".
    """
    m = RunMetrics(expected_tool=expected_tool,
                   expected_server=owners.get(expected_tool, ""))

    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            m.input_tokens += usage.get("input_tokens", 0)
            m.output_tokens += usage.get("output_tokens", 0)
            m.llm_calls += 1
        if getattr(msg, "type", None) == "tool":
            m.tool_result_chars += len(str(msg.content))

    # Tool calls come from the shared renderer, so the number recorded here and
    # the number of lines the room sees on screen cannot drift apart.
    for call in collect_tool_calls(messages):
        m.tool_calls += 1
        name = call["name"]
        m.calls.append({"tool": name, "server": owners.get(name, "?"),
                        "args": {k: str(v)[:60] for k, v in (call["args"] or {}).items()}})

    if m.calls:
        m.first_tool = m.calls[0]["tool"]
        m.first_server = m.calls[0]["server"]
        m.correct = m.first_tool == expected_tool
        m.wrong_server = m.first_server != m.expected_server
        m.recovered = not m.correct and any(c["tool"] == expected_tool for c in m.calls)

    # A clean run is two round-trips: decide-and-call, then answer. Anything
    # past that is the model working around its own first move.
    m.extra_round_trips = max(0, m.llm_calls - 2)
    last = messages[-1]
    m.final_text = last.text if hasattr(last, "text") else str(last.content)
    m.messages = list(messages)
    return m
