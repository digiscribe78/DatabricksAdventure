"""Light homebrew rules: three stats, d20 + modifier against a difficulty class (DC)."""

import random
from dataclasses import asdict, dataclass
from enum import StrEnum


class Stat(StrEnum):
    MIGHT = "might"
    WITS = "wits"
    CHARM = "charm"


DC_EASY = 8
DC_NORMAL = 12
DC_HARD = 16
MIN_DC = 1
MAX_DC = 30


@dataclass(frozen=True)
class CheckResult:
    stat: Stat
    roll: int
    modifier: int
    total: int
    dc: int
    success: bool
    margin: int

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stat"] = self.stat.value
        return d


def roll_d20(rng: random.Random) -> int:
    return rng.randint(1, 20)


def roll_check(stat: Stat, dc: int, modifier: int, rng: random.Random) -> CheckResult:
    """Roll d20 + modifier against ``dc``. Meeting the DC is a success."""
    if not MIN_DC <= dc <= MAX_DC:
        raise ValueError(f"dc must be between {MIN_DC} and {MAX_DC}, got {dc}")
    roll = roll_d20(rng)
    total = roll + modifier
    return CheckResult(
        stat=stat, roll=roll, modifier=modifier, total=total, dc=dc,
        success=total >= dc, margin=total - dc,
    )
