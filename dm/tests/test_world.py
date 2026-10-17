import pytest
from rpg.rules import Stat
from rpg.world import (
    ARCHETYPES, DEFAULT_CHARACTER, LOCATIONS, START_LOCATION_ID, STARTING_GOLD,
    Character, new_character,
)


def test_three_archetypes_match_spec():
    assert set(ARCHETYPES) == {"warrior", "mage", "bard"}
    w, m, b = ARCHETYPES["warrior"], ARCHETYPES["mage"], ARCHETYPES["bard"]
    assert (w.might, w.wits, w.charm, w.max_hp) == (3, 0, 1, 18)
    assert (m.might, m.wits, m.charm, m.max_hp) == (0, 3, 1, 12)
    assert (b.might, b.wits, b.charm, b.max_hp) == (1, 0, 3, 14)


def test_new_character_starts_at_full_hp_with_kit():
    c = new_character("Elowen", "mage")
    assert c.hp == c.max_hp == 12
    assert c.gold == STARTING_GOLD
    assert c.inventory == list(ARCHETYPES["mage"].kit)
    assert c.modifier(Stat.WITS) == 3


def test_new_character_is_case_insensitive_and_trims_name():
    assert new_character("  Brannoc ", "Warrior").name == "Brannoc"


@pytest.mark.parametrize("name,archetype", [("Bob", "paladin"), ("   ", "bard"), ("", "bard")])
def test_new_character_rejects_bad_input(name, archetype):
    with pytest.raises(ValueError):
        new_character(name, archetype)


def test_character_round_trips_through_dict():
    c = new_character("Brannoc", "warrior")
    assert Character.model_validate(c.model_dump()) == c


def test_start_location_exists_and_exits_are_known_ids():
    assert START_LOCATION_ID in LOCATIONS
    for loc in LOCATIONS.values():
        assert loc.description.strip()
        assert all(isinstance(e, str) and e for e in loc.exits)


def test_default_character_is_a_warrior():
    assert DEFAULT_CHARACTER.archetype == "warrior"


def test_defence_is_ten_plus_best_of_might_and_wits():
    assert new_character("A", "warrior").defence == 13
    assert new_character("B", "mage").defence == 13
    assert new_character("C", "bard").defence == 11


def test_eight_locations_with_bible_gates():
    from rpg.world import LOCATIONS

    assert set(LOCATIONS) == {"medallion-inn", "delta-crossing", "unity-archive", "spark-forge",
                              "streaming-falls", "photon-mines", "data-swamp", "silos-keep"}
    archive = LOCATIONS["unity-archive"]
    assert archive.barrier("spark-forge", {}) == "spoke_with_aldric"
    assert archive.barrier("spark-forge", {"spoke_with_aldric": "yes"}) is None
    assert archive.barrier("delta-crossing", {}) is None
    assert LOCATIONS["delta-crossing"].barrier("data-swamp", {}) == "has_catalog"
    assert LOCATIONS["medallion-inn"].barrier("unity-archive", {}) == "knows_cellar_route"
    for loc in LOCATIONS.values():
        assert set(loc.gates) <= set(loc.exits)
        for e in loc.exits:
            assert loc.id in LOCATIONS[e].exits, f"{loc.id}->{e} has no way back"
