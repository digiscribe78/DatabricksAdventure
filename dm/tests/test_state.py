import pytest
from pydantic import ValidationError
from rpg.state import GameState, NpcPresence, apply_changes
from rpg.world import new_character

MARTA = NpcPresence(npc_id="marta-quill", name="Marta Quill", persona="p", speech_style="s",
                    secrets="x", home_location_id="medallion-inn", disposition=0)


def state(**kw):
    base = {"character": new_character("Brannoc", "warrior"), "location_id": "medallion-inn", "npcs": [MARTA]}
    return GameState(**{**base, **kw})


def test_hp_change_clamps_to_max_and_summarises():
    s, notes = apply_changes(state(), [{"kind": "character", "hp_delta": 5}])
    assert s.character.hp == 18
    s, notes = apply_changes(s, [{"kind": "character", "hp_delta": -4}])
    assert s.character.hp == 14 and "HP 18 → 14" in notes


def test_reaching_zero_hp_downs_character_once():
    s, notes = apply_changes(state(location_id="delta-crossing", npcs=[]),
                             [{"kind": "character", "hp_delta": -10}, {"kind": "character", "hp_delta": -40}])
    c = s.character
    assert (c.hp, c.gold, s.location_id) == (9, 6, "medallion-inn")
    assert s.flags["times_downed"] == "1"
    assert sum("downed" in n for n in notes) == 1


def test_items_add_remove_and_missing_item_noted():
    s, notes = apply_changes(state(), [{"kind": "character", "items_add": ["lantern"], "items_remove": ["shield", "crown"]}])
    assert "lantern" in s.character.inventory and "shield" not in s.character.inventory
    assert "+lantern" in notes and "-shield" in notes
    assert any("crown" in n and "not carried" in n for n in notes)


def test_gold_loss_without_purchase_clamps_to_zero():
    s, notes = apply_changes(state(), [{"kind": "character", "gold_delta": -50}])
    assert s.character.gold == 0
    assert any("only had 12" in n for n in notes)


def test_unaffordable_purchase_is_refused_entirely():
    s, notes = apply_changes(state(), [{"kind": "character", "gold_delta": -50, "items_add": ["warhorse"]}])
    assert s.character.gold == 12 and "warhorse" not in s.character.inventory
    assert any("could not afford warhorse" in n for n in notes)


def test_two_lethal_hits_down_only_once():
    s, notes = apply_changes(state(), [{"kind": "character", "hp_delta": -20}, {"kind": "character", "hp_delta": -20}])
    assert (s.character.hp, s.character.gold, s.flags["times_downed"]) == (9, 6, "1")
    assert sum("downed:" in n for n in notes) == 1 and any("already downed" in n for n in notes)


def test_move_after_being_downed_is_ignored():
    s, notes = apply_changes(state(), [{"kind": "character", "hp_delta": -20}, {"kind": "move", "location_id": "delta-crossing"}])
    assert s.location_id == "medallion-inn"
    assert any("already downed" in n for n in notes)


def test_xp_and_flag():
    s, notes = apply_changes(state(), [{"kind": "character", "xp_delta": 5}, {"kind": "flag", "flag": "met_sweeper", "value": "yes"}])
    assert s.character.xp == 5 and s.flags == {"met_sweeper": "yes"}
    assert "XP +5" in notes and "flag met_sweeper = yes" in notes


def test_disposition_clamps():
    s, notes = apply_changes(state(), [{"kind": "disposition", "npc_id": "marta-quill", "delta": 5}])
    assert s.npcs[0].disposition == 3 and "Marta Quill: 0 → 3" in notes


def test_move_to_exit_and_reject_non_exit():
    s, notes = apply_changes(state(), [{"kind": "move", "location_id": "delta-crossing"}])
    assert s.location_id == "delta-crossing" and "moved to The Delta Crossing" in notes
    s2, notes2 = apply_changes(state(), [{"kind": "move", "location_id": "unity-archive"}])
    assert s2.location_id == "medallion-inn" and any("cannot reach" in n for n in notes2)


def test_input_state_is_not_mutated():
    original = state()
    apply_changes(original, [{"kind": "character", "hp_delta": -4, "items_add": ["x"]}])
    assert original.character.hp == 18 and "x" not in original.character.inventory


@pytest.mark.parametrize("bad", [
    {"kind": "teleport"},
    {"kind": "flag", "flag": "Bad Flag!", "value": "x"},
    {"kind": "flag", "flag": "ok", "value": "x" * 81},
])
def test_malformed_changes_rejected(bad):
    with pytest.raises(ValidationError):
        apply_changes(state(), [bad])
