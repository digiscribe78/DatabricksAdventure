"""Eval scenarios: a seeded game state, one player input, and what a good DM turn looks like."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rpg.campaign import CANONICAL_FLAGS
from rpg.world import ARCHETYPES, LOCATIONS

SCENARIOS = Path(__file__).with_name("scenarios.yaml")
DICE_TOOLS = {"roll_check", "resolve_attack", "enemy_attack"}
TOOL_NAMES = DICE_TOOLS | {"search_lore", "move_to", "set_quest_flag", "set_npc_disposition",
                           "update_character", "remember", "recall"}
Category = Literal["check", "combat", "defeat", "lore", "npc", "movement", "bookkeeping", "spoiler", "jailbreak"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a misspelt key must fail, not silently pass


class SeedState(_Strict):
    location_id: str
    archetype: str = "warrior"
    name: str = "Tess"
    hp: int | None = None
    gold: int | None = None
    inventory: list[str] | None = None
    flags: dict[str, str] = Field(default_factory=dict)
    dispositions: dict[str, int] = Field(default_factory=dict)  # only NPCs at location_id


class Expect(_Strict):
    tools: list[str] = Field(default_factory=list)       # every one must be called
    any_tools: list[str] = Field(default_factory=list)   # at least one must be called
    no_tools: list[str] = Field(default_factory=list)    # none may be called
    flags: dict[str, str] = Field(default_factory=dict)  # must hold afterwards
    no_flags: list[str] = Field(default_factory=list)    # must not be set afterwards
    location_id: str | None = None
    guidelines: list[str] = Field(default_factory=list)  # for the ExpectationsGuidelines judge


class Scenario(_Strict):
    id: str
    category: Category
    dice_seed: int = 7
    state: SeedState
    memories: list[str] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    input: str
    expect: Expect = Field(default_factory=Expect)


def load_scenarios(path: Path = SCENARIOS) -> list[Scenario]:
    raw = yaml.safe_load(path.read_text())
    items = raw["scenarios"] if isinstance(raw, dict) else raw  # a bare list is fine too
    scenarios = [Scenario.model_validate(item) for item in items]
    seen: set[str] = set()
    for s in scenarios:
        if s.id in seen:
            raise ValueError(f"duplicate scenario id {s.id}")
        seen.add(s.id)
    return scenarios


def _flag_problem(flag: str, value: str | None) -> str | None:
    if flag not in CANONICAL_FLAGS:
        return f"unknown flag {flag}"
    allowed = CANONICAL_FLAGS[flag]
    if value is not None and allowed and value not in allowed:
        return f"{flag}={value} not in {allowed}"
    return None


def problems(s: Scenario, npc_homes: dict[str, str]) -> list[str]:
    """Everything in a scenario that names something the game doesn't have."""
    found = []
    for where in (s.state.location_id, s.expect.location_id):
        if where is not None and where not in LOCATIONS:
            found.append(f"unknown location {where}")
    if s.state.archetype not in ARCHETYPES:
        found.append(f"unknown archetype {s.state.archetype}")
    flags = [*s.state.flags.items(), *s.expect.flags.items(), *((f, None) for f in s.expect.no_flags)]
    found += [p for f, v in flags if (p := _flag_problem(f, v))]
    found += [f"unknown tool {t}" for t in (*s.expect.tools, *s.expect.any_tools, *s.expect.no_tools)
              if t not in TOOL_NAMES]
    found += [f"{npc} is not at {s.state.location_id}" for npc in s.state.dispositions
              if npc_homes.get(npc) != s.state.location_id]
    return found
