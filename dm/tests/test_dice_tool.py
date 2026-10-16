import random

import agent.tools.dice as dice
import pytest
from agent.tools import all_tools
from rpg.world import new_character

STATE = {"character": new_character("Brannoc", "warrior").model_dump()}


class FixedRng(random.Random):
    def __init__(self, value):
        super().__init__(0)
        self.value = value

    def randint(self, a, b):
        return self.value


@pytest.fixture(autouse=True)
def fixed_dice(monkeypatch):
    monkeypatch.setattr(dice, "RNG", FixedRng(9))


def test_tool_is_auto_registered():
    assert "roll_check" in {t.name for t in all_tools()}


def test_modifier_comes_from_character_state():
    out = dice.roll_check.invoke({"stat": "might", "dc": 12, "reason": "wade the river", "state": STATE})
    assert out == {
        "stat": "might", "roll": 9, "modifier": 3, "total": 12, "dc": 12,
        "success": True, "margin": 0, "reason": "wade the river",
    }


def test_model_cannot_supply_modifier():
    schema = dice.roll_check.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"stat", "dc", "reason"}


@pytest.mark.parametrize("dc", [0, 31])
def test_bad_dc_returns_error_not_exception(dc):
    out = dice.roll_check.invoke({"stat": "wits", "dc": dc, "reason": "x", "state": STATE})
    assert "error" in out and "dc" in out["error"]


def test_missing_character_returns_error():
    out = dice.roll_check.invoke({"stat": "wits", "dc": 12, "reason": "x", "state": {}})
    assert out == {"error": "no character in play"}
