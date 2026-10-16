import random

import pytest
from rpg.rules import DC_HARD, DC_NORMAL, CheckResult, Stat, roll_check, roll_d20


class FixedRng(random.Random):
    """A Random whose randint always returns a fixed value."""

    def __init__(self, value: int):
        super().__init__(0)
        self.value = value

    def randint(self, a: int, b: int) -> int:
        assert (a, b) == (1, 20)
        return self.value


def test_roll_d20_in_range():
    rng = random.Random(42)
    rolls = {roll_d20(rng) for _ in range(500)}
    assert rolls == set(range(1, 21))


def test_check_succeeds_when_total_meets_dc():
    result = roll_check(Stat.MIGHT, DC_NORMAL, modifier=3, rng=FixedRng(9))
    assert result == CheckResult(
        stat=Stat.MIGHT, roll=9, modifier=3, total=12, dc=12, success=True, margin=0
    )


def test_check_fails_below_dc():
    result = roll_check(Stat.WITS, DC_HARD, modifier=0, rng=FixedRng(15))
    assert result.success is False
    assert result.margin == -1


def test_to_dict_is_json_ready():
    d = roll_check(Stat.CHARM, 8, modifier=1, rng=FixedRng(20)).to_dict()
    assert d == {
        "stat": "charm", "roll": 20, "modifier": 1, "total": 21,
        "dc": 8, "success": True, "margin": 13,
    }


@pytest.mark.parametrize("dc", [0, -5, 31, 100])
def test_out_of_range_dc_rejected(dc):
    with pytest.raises(ValueError, match="dc"):
        roll_check(Stat.MIGHT, dc, modifier=0, rng=FixedRng(10))
