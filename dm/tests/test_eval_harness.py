import json

import agent.tools.dice as dice
from evals.harness import make_predict_fn, numbers_in, play_turn, seed_store, stub_memory_tools
from evals.scenarios import Scenario
from langchain_core.messages import AIMessage
from rpg.turn import ComposeOutput

from tests.fakes import ScriptedModel

PROSE = ComposeOutput(narration="Marta eyes you over the bar. " * 6, choices=["Ask about the river", "Order ale"])


def scenario(**over):
    base = {"id": "s1", "category": "bookkeeping", "state": {"location_id": "medallion-inn"}, "input": "I promise."}
    return Scenario.model_validate({**base, **over})


def call(name, idx=0, **args):
    return {"name": name, "args": args, "id": f"c{idx}", "type": "tool_call"}


def test_seed_store_applies_the_scenario_state():
    s = scenario(state={"location_id": "unity-archive", "hp": 5, "gold": 3, "flags": {"vowed_to_find_aldric": "yes"},
                        "dispositions": {"keeper-aldric": 2}})
    game = seed_store(s).load("s1")
    assert (game.location_id, game.character.hp, game.character.gold) == ("unity-archive", 5, 3)
    assert game.flags == {"vowed_to_find_aldric": "yes"}
    assert {n.npc_id: n.disposition for n in game.npcs} == {"keeper-aldric": 2}


def test_numbers_in_walks_nested_values_and_ignores_bools():
    assert numbers_in({"a": [1, "rolled 17 vs 12"], "b": True, "c": 2.0, "d": 2.5}) == {1, 17, 12, 2}


def test_play_turn_records_calls_flags_and_traceable_numbers():
    model = ScriptedModel(replies=[
        AIMessage(content="", tool_calls=[call("roll_check", 0, stat="charm", dc=12, reason="vow"),
                                          call("set_quest_flag", 1, flag="vowed_to_find_aldric", value="yes")]),
        AIMessage(content="ok")], structured=[PROSE])
    out = play_turn(scenario(), model)
    assert out["tool_calls"] == ["roll_check", "set_quest_flag"]
    assert out["flags"] == {"vowed_to_find_aldric": "yes"} and out["location_id"] == "medallion-inn"
    assert out["turn"]["narration"].startswith("Marta")
    assert 12 in out["known_numbers"] and 18 in out["known_numbers"]  # the DC and the warrior's HP


def test_seeded_dice_repeat_and_are_restored():
    def roll():
        model = ScriptedModel(replies=[AIMessage(content="", tool_calls=[call("roll_check", stat="might", dc=12, reason="x")]),
                                       AIMessage(content="ok")], structured=[PROSE])
        play_turn(scenario(dice_seed=3), model)
        return json.loads(model.reason_calls[1][-1].content)["roll"]

    before = dice.RNG
    assert roll() == roll()
    assert dice.RNG is before


def test_memories_reach_the_prompt_and_the_stub_tools_write_nothing():
    memory = "In an earlier adventure the player promised Marta to find Aldric."
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    play_turn(scenario(memories=[memory]), model)
    assert memory in model.reason_calls[0][0].content
    remember, recall = stub_memory_tools([memory])
    assert remember.invoke({"fact": "f", "topic": "t"}) == "stored"
    assert memory in recall.invoke({"query": "vow"})


def test_history_turns_are_played_but_not_scored():
    model = ScriptedModel(replies=[
        AIMessage(content="", tool_calls=[call("roll_check", stat="wits", dc=8, reason="look")]), AIMessage(content="ok"),
        AIMessage(content="ok")], structured=[PROSE, PROSE])
    out = play_turn(scenario(history=["I look around."]), model)
    assert out["tool_calls"] == []
    assert len(model.reason_calls) == 3


def test_predict_fn_returns_narration_and_works_outside_a_trace():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    predict = make_predict_fn([scenario()], model)
    assert predict("s1", "I promise.") == {"narration": PROSE.narration, "choices": PROSE.choices}


def test_play_turn_records_the_guardrail_and_category():
    block = AIMessage(content="This request was blocked by the 'block_jailbreak' service policy.",
                      response_metadata={"finish_reason": "content_filter"})
    model = ScriptedModel(replies=[block], structured=[PROSE])
    out = play_turn(scenario(category="jailbreak"), model)
    assert out["guardrail"] == "block_jailbreak" and out["category"] == "jailbreak"
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    assert play_turn(scenario(), model)["guardrail"] is None
