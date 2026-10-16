"""A scripted stand-in for ChatDatabricks: no network, fully deterministic."""

from collections import deque


class _Structured:
    def __init__(self, parent):
        self.parent = parent

    def invoke(self, messages):
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
        self.reason_calls.append(list(messages))
        return self.replies.popleft()
