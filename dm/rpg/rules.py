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


DAMAGE_DICE = (4, 6, 8, 10, 12)


@dataclass(frozen=True)
class AttackResult:
    roll: int
    modifier: int
    total: int
    defence: int
    hit: bool
    damage_roll: int
    damage: int

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_attack(modifier: int, defence: int, damage_die: int, damage_bonus: int, rng: random.Random) -> AttackResult:
    """One combat exchange: d20 + modifier against defence. A hit deals damage_die + damage_bonus."""
    if damage_die not in DAMAGE_DICE:
        raise ValueError(f"damage_die must be one of {DAMAGE_DICE}, got {damage_die}")
    if not 5 <= defence <= 25:
        raise ValueError(f"defence must be between 5 and 25, got {defence}")
    if not 0 <= damage_bonus <= 5:
        raise ValueError(f"damage_bonus must be between 0 and 5, got {damage_bonus}")
    roll = roll_d20(rng)
    total = roll + modifier
    hit = total >= defence
    damage_roll = rng.randint(1, damage_die) if hit else 0
    return AttackResult(roll, modifier, total, defence, hit, damage_roll, damage_roll + damage_bonus if hit else 0)
