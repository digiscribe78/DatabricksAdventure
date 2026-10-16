import pytest
from pydantic import ValidationError
from rpg.turn import MAX_NARRATION_WORDS, ComposeOutput, TurnEvent, TurnOutput

GOOD = {"narration": "The fire crackles.", "choices": ["Talk to Marta", "Leave"]}


def test_compose_output_accepts_valid():
    c = ComposeOutput(**GOOD)
    assert c.allow_free_text is True


@pytest.mark.parametrize("choices", [[], ["only one"], ["a", "b", "c", "d", "e"], ["a", "  "]])
def test_compose_output_rejects_bad_choices(choices):
    with pytest.raises(ValidationError):
        ComposeOutput(narration="x", choices=choices)


@pytest.mark.parametrize("narration", ["", "   ", "word " * (MAX_NARRATION_WORDS + 1)])
def test_compose_output_rejects_bad_narration(narration):
    with pytest.raises(ValidationError):
        ComposeOutput(narration=narration, choices=["a", "b"])


def test_turn_output_from_compose_carries_code_owned_fields():
    ev = TurnEvent(type="roll", summary="Might check: 9 + 3 = 12 vs DC 12, success")
    t = TurnOutput.from_compose(ComposeOutput(**GOOD), location_id="medallion-inn", events=[ev])
    d = t.model_dump()
    assert d["location_id"] == "medallion-inn"
    assert d["events"][0]["type"] == "roll"
    assert d["game_over"] is None
    assert set(d) == {"narration", "choices", "allow_free_text", "location_id", "events", "game_over"}


def test_turn_event_rejects_unknown_type():
    with pytest.raises(ValidationError):
        TurnEvent(type="teleport", summary="x")
