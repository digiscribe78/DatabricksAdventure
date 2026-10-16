"""A scripted stand-in for ChatDatabricks: no network, fully deterministic."""

from collections import deque

from langchain_core.messages import AIMessage, ToolMessage


def assert_provider_valid(messages):
    """Fail like a real provider would: every tool_call needs a ToolMessage answering it."""
    for i, m in enumerate(messages):
        if isinstance(m, AIMessage) and m.tool_calls:
            answered = {t.tool_call_id for t in messages[i + 1:] if isinstance(t, ToolMessage)}
            missing = [c["id"] for c in m.tool_calls if c["id"] not in answered]
            assert not missing, f"tool_use without tool_result: {missing}"


class _Structured:
    def __init__(self, parent):
        self.parent = parent

    def invoke(self, messages):
        assert_provider_valid(messages)
        self.parent.structured_calls.append(list(messages))
        item = self.parent.structured.popleft()
        if isinstance(item, Exception):
            raise item
        return item


class ScriptedModel:
    """``replies`` are AIMessages returned by dm_reason in order, and ``structured`` are the
    ComposeOutput objects (or Exceptions) returned by compose, in order."""

    def __init__(self, replies=(), structured=()):
        self.replies = deque(replies)
        self.structured = deque(structured)
        self.reason_calls: list[list] = []
        self.structured_calls: list[list] = []

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, schema):
        return _Structured(self)

    def invoke(self, messages):
        assert_provider_valid(messages)
        self.reason_calls.append(list(messages))
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply
