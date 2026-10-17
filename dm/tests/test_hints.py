from rpg.campaign import BEATS
from rpg.hints import HINT_KEY, REQUIRED, load_hints, next_hint

ACT2 = {"vowed_to_find_aldric": "yes", "saw_the_diversion": "yes", "spoke_with_aldric": "yes"}
# Names a hint for an act must not mention: they belong to later acts.
LATER = {1: ["Silo", "Catalog", "Grisle", "Swamp", "Ignatia", "Odo", "Echo"],  # "Silo" covers Silo's Keep
         2: ["Silo's Keep", "Grisle", "Swamp"], 3: []}


def test_every_required_beat_has_both_tiers_and_no_extras():
    hints = load_hints()
    used = {HINT_KEY.get(b, b) for beats in REQUIRED.values() for b in beats}
    assert set(hints) == used
    for key, h in hints.items():
        assert h["nudge"].strip() and h["clearer"].strip(), key


def test_optional_beats_are_not_required():
    for flag in ("knows_cellar_route", "forge_regret_shared", "echo_saw_past_life", "aldric_forgives_silo"):
        assert all(flag not in beats for beats in REQUIRED.values())
    assert set(REQUIRED) == set(BEATS)


def test_hints_never_name_a_later_act():
    hints = load_hints()
    for n, beats in REQUIRED.items():
        for beat in beats:
            h = hints[HINT_KEY.get(beat, beat)]
            for name in LATER[n]:
                assert name not in h["nudge"] + h["clearer"], (beat, name)


def test_act_one_starts_with_the_vow():
    h = next_hint({}, "medallion-inn")
    assert h["beat"] == "vowed_to_find_aldric" and h["where"].startswith("The Medallion Inn")


def test_a_beat_where_you_stand_comes_first():
    assert next_hint({"vowed_to_find_aldric": "yes"}, "unity-archive")["beat"] == "spoke_with_aldric"
    assert next_hint({"vowed_to_find_aldric": "yes"}, "medallion-inn")["beat"] == "saw_the_diversion"


def test_act_two_seals_in_any_order():
    assert next_hint(ACT2, "streaming-falls")["beat"] == "seal_falls"
    assert next_hint({**ACT2, "seal_forge": "yes"}, "unity-archive")["beat"] == "seal_falls"
    h = next_hint({**ACT2, "seal_forge": "yes", "seal_falls": "yes"}, "photon-mines")
    assert h["beat"] in ("seal_mines", "crew_rescued") and "Odo" in h["nudge"] + h["clearer"]


def test_no_hint_once_the_game_is_over():
    assert next_hint({"ending": "wits"}, "silos-keep") is None
    assert next_hint({"defeated_by_silo": "yes"}, "silos-keep") is None
