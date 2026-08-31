"""Token and round-trip accounting, read from LangChain's own message objects.

Nothing here is estimated. Every AI message returned by `create_agent` carries
`usage_metadata` populated straight from the Anthropic API response, so input
and output tokens are the provider's numbers, summed across the whole
trajectory — every turn of the loop, not just the last one.
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
    llm_calls: int = 0          # round-trips to the model
    tool_calls: int = 0
    tool_result_chars: int = 0  # raw bytes the tools pushed back into context
    wall_ms: int = 0
    # What the model actually asked for, in order. The `aggregate` task only
    # pays off if the CLI agent really composes, so record it rather than assume.
    actions: list = field(default_factory=list)
    final_text: str = ""
    correct: bool = False
    # The raw trajectory, kept so the caller can render a tool-call trace after
    # the clock has stopped. Dropped from as_dict(): not JSON-serializable, and
    # `actions` already carries what the committed results need.
    messages: list = field(default_factory=list, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("messages", None)
        d["total_tokens"] = self.total_tokens
        return d


def collect(messages: list, expect: list[str]) -> RunMetrics:
    """Walk an agent trajectory and total up what it actually cost."""
    m = RunMetrics()
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            m.input_tokens += usage.get("input_tokens", 0)
            m.output_tokens += usage.get("output_tokens", 0)
            m.llm_calls += 1
        if getattr(msg, "type", None) == "tool":
            m.tool_result_chars += len(str(msg.content))

    # Tool calls come from the shared renderer, so the number in the results and
    # the number of lines the audience sees on screen cannot drift apart.
    # NOTE: this is the tool-call count, which is NOT the round-trip count —
    # `llm_calls` above is. A turn that calls no tool is still a round-trip you
    # pay input tokens for, so the two are reported separately.
    for call in collect_tool_calls(messages):
        m.tool_calls += 1
        args = call["args"]
        # bash puts the whole command in one arg; MCP tools spread across several.
        m.actions.append(args.get("command") or f"{call['name']}({args})")

    m.messages = list(messages)
    m.final_text = messages[-1].text if hasattr(messages[-1], "text") else str(messages[-1].content)
    haystack = m.final_text.upper().replace(",", "")
    m.correct = all(str(e).upper() in haystack for e in expect)
    return m
