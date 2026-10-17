from collections import Counter
from pathlib import Path

import pytest
from evals.scenarios import Scenario, load_scenarios, problems
from pydantic import ValidationError
from rpg.store import load_npc_cards

NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"
HOMES = {c.npc_id: c.home_location_id for c in load_npc_cards(NPCS)}


def test_every_scenario_names_real_places_flags_tools_and_npcs():
    found = {s.id: problems(s, HOMES) for s in load_scenarios()}
    assert {k: v for k, v in found.items() if v} == {}


def test_categories_match_the_spec():
    counts = Counter(s.category for s in load_scenarios())
    assert counts == {"check": 4, "combat": 3, "defeat": 1, "lore": 4, "npc": 3, "movement": 3,
                      "bookkeeping": 4, "spoiler": 1, "jailbreak": 5}


def test_misspelt_keys_fail_loudly():
    with pytest.raises(ValidationError):
        Scenario.model_validate({"id": "x", "category": "lore", "state": {"location_id": "medallion-inn"},
                                 "input": "hi", "expect": {"no_flag": ["has_catalog"]}})


def test_problems_catches_bad_names():
    s = Scenario.model_validate({
        "id": "x", "category": "lore", "input": "hi",
        "state": {"location_id": "nowhere", "flags": {"met_marta": "yes"}, "dispositions": {"lord-silo": 1}},
        "expect": {"tools": ["teleport"], "flags": {"ending": "victory"}},
    })
    found = " | ".join(problems(s, HOMES))
    for needle in ("nowhere", "met_marta", "teleport", "ending", "lord-silo"):
        assert needle in found


def test_duplicate_ids_are_refused(tmp_path):
    one = "- {id: a, category: lore, state: {location_id: medallion-inn}, input: hi}\n"
    (tmp_path / "s.yaml").write_text(one + one)
    with pytest.raises(ValueError, match="duplicate"):
        load_scenarios(tmp_path / "s.yaml")
