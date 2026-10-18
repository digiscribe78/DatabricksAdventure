"""Models that refuse structured output (Sonnet 5.5 and Opus 5.5 through AI Gateway) still compose a turn."""

from langchain_core.messages import AIMessage
from rpg.turn import ComposeOutput

from tests.fakes import ScriptedModel
from tests.test_dm_graph import PROSE, make, run

REFUSAL = 'Error code: 400 - tool_choice: type "tool" and "any" are not supported for this model.'


class NoStructuredOutput(ScriptedModel):
    """Refuses with_structured_output like the 5.5 models; calls a tool when asked, un-forced."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.compose_prompts = []

    def with_structured_output(self, schema, **kw):
        class Refuses:
            def invoke(self, messages):
                raise ValueError(REFUSAL)
        return Refuses()

    def bind_tools(self, tools, **kw):
        if tools == [ComposeOutput]:
            outer = self

            class Composer:
                def invoke(self, messages):
                    outer.compose_prompts.append((messages, kw))
                    return AIMessage(content="", tool_calls=[{"name": "ComposeOutput", "args": PROSE.model_dump(), "id": "c1", "type": "tool_call"}])
            return Composer()
        return self


def test_a_model_without_structured_output_still_composes_the_turn():
    model = NoStructuredOutput(replies=[AIMessage(content="ok")])
    turn = run(make(model), "I look around.")["turn"]
    assert turn["narration"] == PROSE.narration and turn["choices"] == PROSE.choices
    [(prompt, kw)] = model.compose_prompts
    assert kw.get("tool_choice") == "auto"  # never forced: the 5.5 models refuse that
    assert "ComposeOutput" in prompt[0].content  # the system prompt asks for the tool


def test_other_compose_errors_still_use_the_retry_and_fallback():
    from agent.dm_graph import FALLBACK_NARRATION

    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[RuntimeError("timeout"), RuntimeError("timeout")])
    assert run(make(model), "I look around.")["turn"]["narration"] == FALLBACK_NARRATION
