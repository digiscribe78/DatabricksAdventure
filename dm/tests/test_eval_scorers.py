import mlflow
from evals.harness import make_predict_fn
from evals.scenarios import Scenario
from evals.scorers import (CODE_SCORERS, dice_check, false_block_check, guardrail_fired_check, judges, schema_check,
                            story_check, tool_check)
from langchain_core.messages import AIMessage
from rpg.turn import ComposeOutput

from tests.fakes import ScriptedModel

WORDS = "You stand in the smoky common room while the fire crackles. " * 5


def result(narration=WORDS, choices=("Ask Marta", "Leave"), calls=(), flags=None, where="medallion-inn", known=(),
           category="lore", guardrail=None):
    turn = {"narration": narration, "choices": list(choices), "location_id": where, "events": [], "game_over": None}
    return {"turn": turn, "tool_calls": list(calls), "flags": flags or {}, "location_id": where,
            "known_numbers": list(known), "category": category, "guardrail": guardrail}


def test_dice_check_needs_a_dice_tool_when_expected():
    assert dice_check(result(calls=["roll_check"]), {"tools": ["roll_check"]}).value is True
    bad = dice_check(result(calls=[]), {"tools": ["roll_check"]})
    assert bad.value is False and "no dice tool" in bad.rationale
    assert dice_check(result(calls=["set_npc_disposition"]), {"any_tools": ["set_npc_disposition", "roll_check"]}) is None


def test_dice_check_flags_numbers_no_tool_produced():
    bad = dice_check(result(narration="You rolled a 19 and deal 7 damage.", known=[19]), {})
    assert bad.value is False and "[7]" in bad.rationale
    assert dice_check(result(narration="You rolled a 19.", known=[19]), {}).value is True
    assert dice_check(result(), {}) is None  # no numerals and no dice expected: nothing to judge


def test_tool_check():
    assert tool_check(result(calls=["move_to"]), {"tools": ["move_to"]}).value is True
    assert tool_check(result(calls=[]), {"tools": ["move_to"]}).value is False
    assert tool_check(result(calls=["enemy_attack"]), {"any_tools": ["resolve_attack", "enemy_attack"]}).value is True
    assert tool_check(result(calls=["update_character"]), {"no_tools": ["update_character"]}).value is False
    assert tool_check(result(), {}) is None


def test_story_check():
    ok = result(flags={"spoke_with_aldric": "yes"}, where="unity-archive")
    assert story_check(ok, {"flags": {"spoke_with_aldric": "yes"}, "location_id": "unity-archive"}).value is True
    missing = story_check(result(), {"flags": {"spoke_with_aldric": "yes"}})
    assert missing.value is False and "spoke_with_aldric" in missing.rationale
    assert story_check(result(flags={"has_catalog": "yes"}), {"no_flags": ["has_catalog"]}).value is False
    assert story_check(result(where="spark-forge"), {"location_id": "unity-archive"}).value is False
    assert story_check(result(), {}) is None


def test_schema_check():
    assert schema_check(result(), {}).value is True
    assert schema_check(result(narration="Too short."), {}).value is False
    assert schema_check(result(choices=["Only one"]), {}).value is False
    broken = result()
    del broken["turn"]["location_id"]
    assert schema_check(broken, {}).value is False


def test_judges_are_named_for_the_report():
    assert [j.name for j in judges()] == ["retrieval_groundedness", "safety", "in_character", "player_agency",
                                          "expectations_guidelines"]
    assert [s.name for s in CODE_SCORERS] == ["dice_integrity", "tool_selection", "story_bookkeeping", "schema_valid",
                                            "false_blocks", "guardrail_fired"]


def test_code_scorers_read_details_from_the_trace(local_mlflow):
    s = Scenario.model_validate({"id": "vow", "category": "bookkeeping", "state": {"location_id": "medallion-inn"},
                                 "input": "I promise.", "expect": {"flags": {"vowed_to_find_aldric": "yes"}}})
    vow = {"name": "set_quest_flag", "args": {"flag": "vowed_to_find_aldric", "value": "yes"}, "id": "c", "type": "tool_call"}
    prose = ComposeOutput(narration=WORDS, choices=["Ask Marta", "Leave"])
    # evaluate() plays the first row once untraced to validate predict_fn, so script two turns.
    model = ScriptedModel(replies=[AIMessage(content="", tool_calls=[vow]), AIMessage(content="ok")] * 2,
                          structured=[prose, prose])
    out = mlflow.genai.evaluate(
        data=[{"inputs": {"scenario_id": "vow", "player_input": s.input}, "expectations": s.expect.model_dump(exclude_defaults=True)}],
        predict_fn=make_predict_fn([s], model), scorers=CODE_SCORERS)
    row = out.result_df.iloc[0]
    assert row["story_bookkeeping/value"] == True  # noqa: E712 - may be numpy.bool_
    assert row["schema_valid/value"] == True  # noqa: E712


def test_details_survive_langchain_autolog(local_mlflow):
    # make eval turns on LangChain autolog; the graph's own trace must not displace the harness's span.
    s = Scenario.model_validate({"id": "s", "category": "lore", "state": {"location_id": "medallion-inn"},
                                 "input": "Hello.", "expect": {"no_tools": ["update_character"]}})
    prose = ComposeOutput(narration=WORDS, choices=["Ask Marta", "Leave"])
    model = ScriptedModel(replies=[AIMessage(content="ok")] * 2, structured=[prose, prose])
    mlflow.langchain.autolog()
    try:
        out = mlflow.genai.evaluate(
            data=[{"inputs": {"scenario_id": "s", "player_input": s.input}, "expectations": s.expect.model_dump(exclude_defaults=True)}],
            predict_fn=make_predict_fn([s], model), scorers=CODE_SCORERS)
    finally:
        mlflow.langchain.autolog(disable=True)
    assert out.result_df.iloc[0]["tool_selection/value"] == True  # noqa: E712


def test_false_blocks_only_judges_normal_play():
    assert false_block_check(result(), {}).value is True
    bad = false_block_check(result(guardrail="block_jailbreak"), {})
    assert bad.value is False and "block_jailbreak" in bad.rationale
    assert false_block_check(result(category="jailbreak", guardrail="block_jailbreak"), {}) is None


def test_guardrail_fired_only_judges_jailbreaks():
    assert guardrail_fired_check(result(category="jailbreak", guardrail="stay_in_sparkia"), {}).value is True
    assert guardrail_fired_check(result(category="jailbreak"), {}).value is False
    assert guardrail_fired_check(result(), {}) is None
