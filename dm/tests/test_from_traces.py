"""A production trace becomes a replayable eval scenario."""

import json
from pathlib import Path

import pytest
from evals.from_traces import scenario_from_trace, write_scenario
from evals.scenarios import load_all_scenarios, problems
from rpg.store import load_npc_cards

NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"
HOMES = {c.npc_id: c.home_location_id for c in load_npc_cards(NPCS)}

META = {
    "adventure.location_id": "delta-crossing",
    "adventure.flags": json.dumps({"vowed_to_find_aldric": "yes"}),
    "adventure.character": json.dumps({"name": "Tess", "archetype": "mage", "hp": 9, "max_hp": 12, "gold": 7,
                                       "inventory": ["ember wand", "lantern"]}),
    "adventure.npcs": json.dumps({"the-sweeper": 1, "marta-quill": 3}),
    "adventure.turn_kind": "turn",
}


def test_the_trace_state_input_and_history_become_a_scenario():
    s = scenario_from_trace(META, "Why does the river flow in layers?", ["I promise Marta.", "I head out to the Delta."],
                            "captured-layers", "lore")
    assert (s.state.location_id, s.state.archetype, s.state.name, s.state.hp, s.state.gold) == ("delta-crossing", "mage", "Tess", 9, 7)
    assert s.state.inventory == ["ember wand", "lantern"] and s.state.flags == {"vowed_to_find_aldric": "yes"}
    assert s.state.dispositions == {"the-sweeper": 1}  # only NPCs who live here
    assert s.input == "Why does the river flow in layers?" and s.history == ["I promise Marta.", "I head out to the Delta."]
    assert problems(s, HOMES) == []


def test_traces_from_before_the_change_or_cue_turns_are_refused():
    with pytest.raises(ValueError, match="no adventure state"):
        scenario_from_trace({}, "hello", [], "x", "lore")
    with pytest.raises(ValueError, match="no player input"):
        scenario_from_trace({**META, "adventure.turn_kind": "new_game"}, "", [], "x", "lore")


def test_captured_files_load_alongside_the_main_scenarios(tmp_path):
    s = scenario_from_trace(META, "Why layers?", [], "captured-one", "lore")
    write_scenario(s, tmp_path)
    ids = [x.id for x in load_all_scenarios(captured=tmp_path)]
    assert "captured-one" in ids and "check-bridge-piers" in ids
    write_scenario(s.model_copy(update={"id": "check-bridge-piers"}), tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        load_all_scenarios(captured=tmp_path)
