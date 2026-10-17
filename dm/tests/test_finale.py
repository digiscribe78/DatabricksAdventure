"""The finale's endings are decided in code: the DM narrates, the realm records."""

import agent.tools.dice as dice
from agent.tools.dice import roll_check
from langchain_core.messages import AIMessage
from rpg.campaign import finale_dcs, finale_ending, story_so_far
from rpg.state import GameState, apply_changes
from rpg.world import new_character

from tests.fakes import ScriptedModel
from tests.test_dm_graph import PROSE, FixedRng, make, new_store, run, tc

ACT3 = {"vowed_to_find_aldric": "yes", "saw_the_diversion": "yes", "spoke_with_aldric": "yes", "seal_forge": "yes",
        "seal_falls": "yes", "seal_mines": "yes", "crew_rescued": "yes", "has_catalog": "yes", "grisle_outcome": "bluffed"}


def keep(**flags):
    return GameState(character=new_character("Tess", "warrior"), location_id="silos-keep", flags={**ACT3, **flags}, npcs=[])


def roll(stat, dc, success):
    return {"stat": stat, "dc": dc, "success": success}


def test_the_third_wound_ends_it_by_might():
    s, notes = apply_changes(keep(silo_wounds="2"), [{"kind": "flag", "flag": "silo_wounds", "value": "3"}])
    assert s.flags["ending"] == "might" and "Lord Silo yields to your might" in notes


def test_finale_dcs_follow_the_story():
    assert finale_dcs(ACT3) == {"wits": 16, "charm": None}
    assert finale_dcs({**ACT3, "forge_regret_shared": "yes", "aldric_forgives_silo": "yes"}) == {"wits": 12, "charm": 16}
    assert finale_dcs({**ACT3, "aldric_forgives_silo": "yes", "marta_trusts_you": "yes"})["charm"] == 12


def test_a_hard_enough_wits_or_charm_success_ends_it():
    assert finale_ending(ACT3, "silos-keep", [roll("wits", 16, True)]) == "wits"
    forgiven = {**ACT3, "aldric_forgives_silo": "yes"}
    assert finale_ending(forgiven, "silos-keep", [roll("charm", 16, True)]) == "charm"


def test_failures_easy_rolls_and_wrong_places_do_not():
    assert finale_ending(ACT3, "silos-keep", [roll("wits", 16, False)]) is None
    assert finale_ending(ACT3, "silos-keep", [roll("wits", 10, True)]) is None  # too easy to count
    assert finale_ending(ACT3, "silos-keep", [roll("charm", 16, True)]) is None  # Aldric hasn't forgiven Silo
    assert finale_ending(ACT3, "data-swamp", [roll("wits", 16, True)]) is None
    assert finale_ending({k: v for k, v in ACT3.items() if k != "has_catalog"}, "silos-keep", [roll("wits", 16, True)]) is None
    assert finale_ending({**ACT3, "ending": "might"}, "silos-keep", [roll("wits", 16, True)]) is None


def test_the_dm_is_told_the_realm_records_the_ending():
    assert "the realm records the ending itself" in story_so_far(ACT3, "silos-keep")


def test_a_winning_wits_roll_in_the_keep_ends_the_game_turn(monkeypatch):
    monkeypatch.setattr(dice, "RNG", FixedRng(20))
    store = new_store()
    game = store.load("t1")
    store.commit("t1", game.model_copy(update={"location_id": "silos-keep", "flags": dict(ACT3)}))
    model = ScriptedModel(replies=[AIMessage(content="", tool_calls=[tc("roll_check", stat="wits", dc=16, reason="the Catalog's proof")]),
                                   AIMessage(content="draft")], structured=[PROSE])
    turn = run(make(model, [roll_check], store), "I lay the Lost Catalog before Lord Silo.")["turn"]
    assert turn["game_over"] == "victory"
    assert store.load("t1").flags["ending"] == "wits"
    assert any("Lord Silo yields to your wits" in e["summary"] for e in turn["events"] if e["type"] == "state")
