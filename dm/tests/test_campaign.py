from rpg.campaign import CANONICAL_FLAGS, CODE_FLAGS, FLAG_HINTS, SEALS, act, game_over, story_so_far, validate_flag


def test_canonical_flags_match_the_bible():
    assert set(SEALS) <= set(CANONICAL_FLAGS)
    for f in ["vowed_to_find_aldric", "saw_the_diversion", "spoke_with_aldric", "knows_cellar_route",
              "forge_regret_shared", "echo_saw_past_life", "crew_rescued", "has_catalog",
              "aldric_forgives_silo", "grisle_outcome", "silo_wounds", "ending"]:
        assert f in CANONICAL_FLAGS, f
    assert CANONICAL_FLAGS["grisle_outcome"] == ("fought", "bribed", "bluffed")
    assert CANONICAL_FLAGS["ending"] == ("might", "wits", "charm")


def test_validate_flag():
    assert validate_flag("seal_forge", "yes") is None
    assert "unknown" in validate_flag("met_marta", "yes")
    assert "must be one of" in validate_flag("ending", "victory")
    assert "set by the realm" in validate_flag("defeated_by_silo", "yes")
    assert CODE_FLAGS == {"times_downed", "marta_trusts_you", "defeated_by_silo"}


def test_acts():
    assert act({}) == 1
    assert act({"spoke_with_aldric": "yes"}) == 2
    assert act({"spoke_with_aldric": "yes", **{s: "yes" for s in SEALS}}) == 3
    assert act({"has_catalog": "yes"}) == 3


def test_story_so_far_tracks_progress():
    one = story_so_far({"vowed_to_find_aldric": "yes"}, "medallion-inn")
    assert one.startswith("Act 1") and "Unity Archive" in one and "vowed" in one
    two = story_so_far({"spoke_with_aldric": "yes", "seal_forge": "yes"}, "unity-archive")
    assert two.startswith("Act 2") and "Forge ✓" in two and "Falls ✗" in two and "Mines ✗" in two
    ready = story_so_far({"spoke_with_aldric": "yes", **{s: "yes" for s in SEALS}}, "photon-mines")
    assert ready.startswith("Act 3") and "open the vault" in ready
    carrying = story_so_far({"has_catalog": "yes"}, "delta-crossing")
    assert "downstream ferry" in carrying
    finale = story_so_far({"has_catalog": "yes", "silo_wounds": "1", "forge_regret_shared": "yes"}, "silos-keep")
    assert "Finale" in finale and "wounds 1/3" in finale and "Wits DC 12" in finale and "Charm: not yet possible" in finale


def test_game_over():
    assert game_over({}) is None
    assert game_over({"ending": "charm"}) == "victory"
    assert game_over({"defeated_by_silo": "yes"}) == "defeat"


def test_every_gate_flag_has_an_in_world_hint():
    from rpg.world import LOCATIONS

    for loc in LOCATIONS.values():
        for flag in loc.gates.values():
            assert flag in FLAG_HINTS and "_" not in FLAG_HINTS[flag]
