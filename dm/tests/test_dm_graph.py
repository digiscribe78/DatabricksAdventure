import random

import agent.tools.dice as dice
import pytest
from agent.dm_graph import FALLBACK_NARRATION, MAX_TOOL_CALLS_PER_TURN, build_dm_graph
from agent.tools.dice import roll_check
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from rpg.turn import ComposeOutput
from rpg.world import START_LOCATION_ID

from tests.fakes import ScriptedModel

PROSE = ComposeOutput(narration="Marta eyes you over the bar.", choices=["Ask about the river", "Order ale"])


class FixedRng(random.Random):
    def __init__(self, v):
        super().__init__(0)
        self.v = v

    def randint(self, a, b):
        return self.v


@pytest.fixture(autouse=True)
def fixed_dice(monkeypatch):
    monkeypatch.setattr(dice, "RNG", FixedRng(15))


def call(name="roll_check", idx=0, **args):
    args = args or {"stat": "charm", "dc": 12, "reason": "haggle"}
    return {"name": name, "args": args, "id": f"call-{idx}", "type": "tool_call"}


def run(graph, content, thread="t1"):
    msgs = [] if content is None else [{"role": "user", "content": content}]
    return graph.invoke({"messages": msgs}, {"configurable": {"thread_id": thread}})


def make(model):
    return build_dm_graph(model, [roll_check], checkpointer=InMemorySaver())


def test_plain_turn_returns_valid_turn_output():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    out = run(make(model), "I look around.")
    turn = out["turn"]
    assert turn["narration"] == PROSE.narration
    assert turn["choices"] == PROSE.choices
    assert turn["location_id"] == START_LOCATION_ID
    assert turn["events"] == []
    assert isinstance(out["messages"][-1], AIMessage)


def test_tool_roll_becomes_code_built_event():
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[call()]), AIMessage(content="done")],
        structured=[PROSE],
    )
    turn = run(make(model), "I haggle with Marta.")["turn"]
    assert len(turn["events"]) == 1
    ev = turn["events"][0]
    assert ev["type"] == "roll"
    assert ev["detail"]["total"] == 16  # 15 + Warrior charm +1
    assert "15" in ev["summary"] and "16" in ev["summary"] and "DC 12" in ev["summary"]


def test_dm_system_prompt_includes_character_and_location():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), "Hello")
    system = model.reason_calls[0][0]
    assert isinstance(system, SystemMessage)
    assert "Brannoc" in system.content and "Medallion Inn" in system.content


def test_tool_budget_stops_runaway_loop_and_drops_unanswered_call():
    looping = [AIMessage(content="", tool_calls=[call(idx=i)]) for i in range(MAX_TOOL_CALLS_PER_TURN + 1)]
    model = ScriptedModel(replies=looping, structured=[PROSE])
    out = run(make(model), "I keep rolling.")
    tool_msgs = [m for m in out["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == MAX_TOOL_CALLS_PER_TURN
    compose_input = model.structured_calls[0]
    last_non_system = [m for m in compose_input if not isinstance(m, SystemMessage)][-1]
    assert not getattr(last_non_system, "tool_calls", None)
    assert len(out["turn"]["events"]) == MAX_TOOL_CALLS_PER_TURN


def test_bad_tool_args_do_not_crash_turn():
    bad = call(stat="strength", dc=12, reason="x")
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[bad]), AIMessage(content="done")],
        structured=[PROSE],
    )
    out = run(make(model), "I flex.")
    assert out["turn"]["narration"] == PROSE.narration
    assert out["turn"]["events"] == []


def test_structured_output_retries_once_then_succeeds():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[ValueError("bad json"), PROSE])
    turn = run(make(model), "Hi")["turn"]
    assert turn["narration"] == PROSE.narration
    assert len(model.structured_calls) == 2


def test_structured_output_double_failure_gives_fallback_turn():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[ValueError("x"), ValueError("y")])
    turn = run(make(model), "Hi")["turn"]
    assert turn["narration"] == FALLBACK_NARRATION
    assert 2 <= len(turn["choices"]) <= 4


def test_fallback_reuses_previous_choices():
    model = ScriptedModel(
        replies=[AIMessage(content="ok"), AIMessage(content="ok")],
        structured=[PROSE, ValueError("x"), ValueError("y")],
    )
    graph = make(model)
    run(graph, "Hi")
    turn = run(graph, "Again")["turn"]
    assert turn["choices"] == PROSE.choices


def test_empty_first_invocation_sets_opening_scene():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), None)
    sent = model.reason_calls[0]
    assert isinstance(sent[-1], HumanMessage)


def test_state_persists_across_turns_in_a_session():
    model = ScriptedModel(
        replies=[AIMessage(content="ok"), AIMessage(content="ok")], structured=[PROSE, PROSE]
    )
    graph = make(model)
    first = run(graph, "Hi")
    second = run(graph, "Hello again")
    assert second["character"] == first["character"]
    assert second["location_id"] == START_LOCATION_ID
    humans = [m for m in second["messages"] if isinstance(m, HumanMessage)]
    assert [h.content for h in humans] == ["Hi", "Hello again"]
