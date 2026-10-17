"""Tools that stage changes to the saved game. Nothing is written until commit_state ends the turn."""

import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import ValidationError

from rpg.campaign import FLAG_HINTS, check_flag, validate_flag
from rpg.state import CharacterChange, DispositionChange, FlagChange, MoveChange
from rpg.world import LOCATIONS

State = Annotated[dict, InjectedState]
CallId = Annotated[str, InjectedToolCallId]


def reply(name: str, tool_call_id: str, content: dict, change: dict | None = None) -> Command:
    update: dict = {"messages": [ToolMessage(json.dumps(content), name=name, tool_call_id=tool_call_id)]}
    if change is not None:
        update["staged"] = [change]
    return Command(update=update)


def _stage(name: str, tool_call_id: str, model_cls, **fields) -> Command:
    try:
        change = model_cls(**fields).model_dump()
    except ValidationError as e:
        return reply(name, tool_call_id, {"error": e.errors()[0]["msg"]})
    return reply(name, tool_call_id, {"staged": change}, change)


@tool
def update_character(
    state: State, tool_call_id: CallId, hp_delta: int = 0, gold_delta: int = 0, xp_delta: int = 0,
    items_add: list[str] | None = None, items_remove: list[str] | None = None, reason: str = "",
) -> Command:
    """Change the player character's HP, gold, XP or inventory: healing, non-combat harm, buying,
    paying, finding, losing or using up items, or rewards. Changes apply at the end of the turn."""
    items_add, items_remove = items_add or [], items_remove or []
    problems = [
        abs(hp_delta) > 50 and "hp_delta must be between -50 and 50",
        abs(gold_delta) > 1000 and "gold_delta must be between -1000 and 1000",
        not 0 <= xp_delta <= 100 and "xp_delta must be between 0 and 100",
        (len(items_add) > 5 or len(items_remove) > 5) and "at most 5 items at a time",
        any(len(i) > 40 or not i.strip() for i in [*items_add, *items_remove]) and "item names must be 1-40 characters",
    ]
    if errors := [p for p in problems if p]:
        return reply("update_character", tool_call_id, {"error": "; ".join(errors)})
    return _stage("update_character", tool_call_id, CharacterChange, hp_delta=hp_delta, gold_delta=gold_delta,
                  xp_delta=xp_delta, items_add=items_add, items_remove=items_remove)


@tool
def set_quest_flag(flag: str, value: str, state: State, tool_call_id: CallId) -> Command:
    """Record story progress as a snake_case flag, e.g. met_the_sweeper = yes or archive_door = forced."""
    problem = validate_flag(flag, value) or check_flag(flag, value, state.get("flags") or {}, state.get("location_id", ""))
    if problem:
        return reply("set_quest_flag", tool_call_id, {"error": problem})
    return _stage("set_quest_flag", tool_call_id, FlagChange, flag=flag, value=value)


@tool
def set_npc_disposition(npc_id: str, delta: int, reason: str, state: State, tool_call_id: CallId) -> Command:
    """Shift how an NPC who is present feels about the player: +1 or +2 when helped or charmed,
    -1 or -2 when insulted or cheated."""
    present = [n["npc_id"] for n in state.get("npcs", [])]
    if npc_id not in present:
        return reply("set_npc_disposition", tool_call_id, {"error": f"{npc_id} is not here; present: {present}"})
    if not -2 <= delta <= 2:
        return reply("set_npc_disposition", tool_call_id, {"error": "delta must be between -2 and 2"})
    return _stage("set_npc_disposition", tool_call_id, DispositionChange, npc_id=npc_id, delta=delta)


@tool
def move_to(location_id: str, state: State, tool_call_id: CallId) -> Command:
    """Move the player to a neighbouring location when they travel there. Only the current location's exits are reachable."""
    here = LOCATIONS[state["location_id"]]
    if location_id not in here.exits:
        return reply("move_to", tool_call_id, {"error": f"cannot reach {location_id}; exits: {list(here.exits)}"})
    barrier = here.barrier(location_id, state.get("flags") or {})
    if barrier:
        name = LOCATIONS[location_id].name
        return reply("move_to", tool_call_id, {"error": f"The way to {name} is barred: {FLAG_HINTS.get(barrier, 'the way is shut')}."})
    return _stage("move_to", tool_call_id, MoveChange, location_id=location_id)
