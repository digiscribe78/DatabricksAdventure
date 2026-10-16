"""The DM's built-in locations must agree with the content manifest the lore index is built from."""

from pathlib import Path

import yaml
from rpg.world import LOCATIONS

MANIFEST = Path(__file__).resolve().parents[2] / "content" / "manifest.yaml"


def load():
    return yaml.safe_load(MANIFEST.read_text())


def test_manifest_locations_match_world():
    m = load()
    assert {loc["id"]: tuple(loc["exits"]) for loc in m["locations"]} == {
        loc.id: loc.exits for loc in LOCATIONS.values()
    }


def test_every_document_file_exists_and_is_typed():
    m = load()
    lore_dir = MANIFEST.parent / "lore"
    for doc in m["documents"]:
        assert (lore_dir / doc["file"]).is_file(), doc["file"]
        assert doc["doc_type"] in {"location", "primer", "rules", "bestiary"}
        if doc["doc_type"] == "location":
            assert doc["location_id"] in LOCATIONS
        else:
            assert doc["location_id"] == "global"


def test_every_location_has_a_lorebook_document():
    m = load()
    files = {d["file"]: d for d in m["documents"]}
    for loc in m["locations"]:
        assert files[loc["lorebook"]]["location_id"] == loc["id"]
