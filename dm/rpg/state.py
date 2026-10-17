"""Game state and the changes the DM may stage. apply_changes is pure: same input, same output."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from rpg.campaign import FLAG_HINTS, check_flag, game_over, validate_flag
from rpg.world import LOCATIONS, START_LOCATION_ID, Character

FLAG_PATTERN = r"^[a-z][a-z0-9_]{0,47}$"


class NpcCard(BaseModel):
    npc_id: str
    name: str
    persona: str
    speech_style: str
    secrets: str
    home_location_id: str
    reveal_after: str | None = None  # a flag that must be "yes" before the DM may know the secret


class NpcPresence(NpcCard):
    disposition: int = 0


class GameState(BaseModel):
    character: Character
    location_id: str
    flags: dict[str, str] = Field(default_factory=dict)
    npcs: list[NpcPresence] = Field(default_factory=list)


class CharacterChange(BaseModel):
    kind: Literal["character"] = "character"
    hp_delta: int = 0
    xp_delta: int = 0
    gold_delta: int = 0
    items_add: list[str] = Field(default_factory=list)
    items_remove: list[str] = Field(default_factory=list)


class FlagChange(BaseModel):
    kind: Literal["flag"] = "flag"
    flag: str = Field(pattern=FLAG_PATTERN)
    value: str = Field(max_length=80)


class DispositionChange(BaseModel):
    kind: Literal["disposition"] = "disposition"
    npc_id: str
    delta: int


class MoveChange(BaseModel):
    kind: Literal["move"] = "move"
    location_id: str


Change = Annotated[Union[CharacterChange, FlagChange, DispositionChange, MoveChange], Field(discriminator="kind")]
_CHANGES = TypeAdapter(list[Change])


def _apply_character(state: GameState, ch: CharacterChange, notes: list[str]) -> None:
    c = state.character
    if ch.items_add and ch.gold_delta < 0 and c.gold + ch.gold_delta < 0:
        notes.append(f"could not afford {', '.join(ch.items_add)}: wanted {-ch.gold_delta} gold, had {c.gold}")
        return
    if ch.hp_delta:
        new_hp = max(0, min(c.max_hp, c.hp + ch.hp_delta))
        notes.append(f"HP {c.hp} → {new_hp}")
        c.hp = new_hp
    if ch.xp_delta:
        c.xp = max(0, c.xp + ch.xp_delta)
        notes.append(f"XP {ch.xp_delta:+d}")
    if ch.gold_delta:
        if c.gold + ch.gold_delta < 0:
            notes.append(f"wanted {-ch.gold_delta} gold but only had {c.gold}")
        new_gold = max(0, c.gold + ch.gold_delta)
        notes.append(f"Gold {c.gold} → {new_gold}")
        c.gold = new_gold
    for item in ch.items_add:
        c.inventory.append(item)
        notes.append(f"+{item}")
    for item in ch.items_remove:
        if item in c.inventory:
            c.inventory.remove(item)
            notes.append(f"-{item}")
        else:
            notes.append(f"{item} not carried")


def _downed(state: GameState, notes: list[str]) -> None:
    c = state.character
    if state.location_id == "silos-keep":
        state.flags["defeated_by_silo"] = "yes"
        notes.append("defeated by Lord Silo: the walls close over you")
        return
    c.hp = c.max_hp // 2
    c.gold = c.gold // 2
    state.location_id = START_LOCATION_ID
    state.flags["times_downed"] = str(int(state.flags.get("times_downed", "0")) + 1)
    notes.append(f"downed: woke at {LOCATIONS[START_LOCATION_ID].name} with HP {c.hp} and {c.gold} gold")


def apply_changes(state: GameState, changes: list[dict]) -> tuple[GameState, list[str]]:
    parsed = _CHANGES.validate_python(changes)
    if outcome := game_over(state.flags):
        return state.model_copy(deep=True), [f"the adventure is over ({outcome}): nothing more changes"]
    new = state.model_copy(deep=True)
    notes: list[str] = []
    downed = False
    for ch in parsed:
        if downed and isinstance(ch, CharacterChange) and ch.hp_delta < 0:
            notes.append("already downed, further harm ignored")
            ch = ch.model_copy(update={"hp_delta": 0})
        if downed and isinstance(ch, MoveChange):
            notes.append(f"already downed, stayed at {LOCATIONS[new.location_id].name}")
            continue
        if isinstance(ch, CharacterChange):
            _apply_character(new, ch, notes)
            if new.character.hp == 0 and not downed:
                _downed(new, notes)
                downed = True
        elif isinstance(ch, FlagChange):
            problem = validate_flag(ch.flag, ch.value, new.flags) or check_flag(ch.flag, ch.value, new.flags, new.location_id)
            if problem:
                notes.append(f"ignored flag {ch.flag}: {problem}")
                continue
            new.flags[ch.flag] = ch.value
            notes.append(f"flag {ch.flag} = {ch.value}")
            if ch.flag == "silo_wounds" and ch.value == "3" and "ending" not in new.flags:
                new.flags["ending"] = "might"  # the third wound ends it: code decides, as with defeat
                notes.append("Lord Silo yields to your might")
            elif ch.flag == "ending":
                notes.append(f"Lord Silo yields to your {ch.value}")
        elif isinstance(ch, DispositionChange):
            for npc in new.npcs:
                if npc.npc_id == ch.npc_id:
                    after = max(-3, min(3, npc.disposition + ch.delta))
                    notes.append(f"{npc.name}: {npc.disposition} → {after}")
                    npc.disposition = after
                    if npc.npc_id == "marta-quill" and after >= 1 and new.flags.get("marta_trusts_you") != "yes":
                        new.flags["marta_trusts_you"] = "yes"
                        notes.append("Marta Quill now trusts you")
        elif isinstance(ch, MoveChange):
            here = LOCATIONS[new.location_id]
            barrier = here.barrier(ch.location_id, new.flags)
            if ch.location_id not in here.exits or ch.location_id not in LOCATIONS:
                notes.append(f"cannot reach {ch.location_id} from {here.name}")
            elif barrier:
                notes.append(f"barred from {LOCATIONS[ch.location_id].name}: {FLAG_HINTS.get(barrier, 'the way is shut')}")
            else:
                new.location_id = ch.location_id
                notes.append(f"moved to {LOCATIONS[ch.location_id].name}")
    return new, notes
