"""Dice tool: the DM calls this for any uncertain outcome instead of inventing a result."""

import random
from typing import Annotated, Literal

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from agent.tools.state_tools import reply
from rpg import rules
from rpg.state import CharacterChange
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


@tool
def resolve_attack(
    stat: Literal["might", "wits"], target: str, target_defence: int, damage_die: int, damage_bonus: int,
    state: Annotated[dict, InjectedState],
) -> dict:
    """The player attacks a creature. Use might for weapons and wits for spells. Take the target's
    defence from the bestiary, and the player's weapon damage from the rules (longsword or ember
    wand: die 6, bonus 2; rapier: die 6, bonus 1). Track the creature's wounds in your narration."""
    character = Character.model_validate(state["character"])
    try:
        result = rules.resolve_attack(character.modifier(rules.Stat(stat)), target_defence, damage_die, damage_bonus, RNG)
    except ValueError as e:
        return {"error": str(e)}
    return {**result.to_dict(), "target": target}


@tool
def enemy_attack(
    attacker: str, attack_bonus: int, damage_die: int, damage_bonus: int,
    state: Annotated[dict, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """A creature attacks the player. Use its attack bonus and damage from the bestiary. The
    player's defence and any damage to their HP are applied automatically."""
    character = Character.model_validate(state["character"])
    if not 0 <= attack_bonus <= 10:
        return reply("enemy_attack", tool_call_id, {"error": "attack_bonus must be between 0 and 10"})
    try:
        result = rules.resolve_attack(attack_bonus, character.defence, damage_die, damage_bonus, RNG)
    except ValueError as e:
        return reply("enemy_attack", tool_call_id, {"error": str(e)})
    content = {**result.to_dict(), "attacker": attacker, "target": character.name}
    if not result.hit:
        return reply("enemy_attack", tool_call_id, content)
    change = CharacterChange(hp_delta=-result.damage).model_dump()
    return reply("enemy_attack", tool_call_id, {**content, "staged": change}, change)
