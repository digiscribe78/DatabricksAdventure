"""Dice tool: the DM calls this for any uncertain outcome instead of inventing a result."""

import random
from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from rpg import rules
from rpg.world import Character

RNG: random.Random = random.SystemRandom()


@tool
def roll_check(
    stat: Literal["might", "wits", "charm"],
    dc: int,
    reason: str,
    state: Annotated[dict, InjectedState],
) -> dict:
    """Roll a d20 skill check for the player's character.

    Use this whenever the outcome of the player's action is uncertain. Choose the stat that fits
    (might = strength and force, wits = magic, knowledge and perception, charm = persuasion and
    deceit) and a difficulty: 8 easy, 12 normal, 16 hard. Narrate the result you get back. Never
    invent a roll.
    """
    raw = state.get("character")
    if not raw:
        return {"error": "no character in play"}
    character = Character.model_validate(raw)
    stat_enum = rules.Stat(stat)
    try:
        result = rules.roll_check(stat_enum, dc, character.modifier(stat_enum), RNG)
    except ValueError as e:
        return {"error": str(e)}
    return {**result.to_dict(), "reason": reason}
