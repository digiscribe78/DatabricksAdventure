"""Content contract: the story bible's facts must be in the lorebooks the DM retrieves."""

import re
from pathlib import Path

import pytest
from rpg.campaign import CANONICAL_FLAGS, CODE_FLAGS
from rpg.world import LOCATIONS

LORE = Path(__file__).resolve().parents[2] / "content" / "lore"

MUST_INCLUDE = {
    "medallion-inn": ["Marta Quill", "cellar", "running water", "ledger"],
    "delta-crossing": ["the Sweeper", "downstream", "older current"],
    "unity-archive": ["writ", "Keeper Aldric", "three seals", "vault", "undercroft"],
    "spark-forge": ["Trial of Kindling", "Ignatia Vale", "spark", "Forge Seal"],
    "streaming-falls": ["the Echo", "echoes", "choices", "Falls Seal"],
    "photon-mines": ["chalk", "Odo Brack", "crew", "Mines Seal"],
    "data-swamp": ["Warden Grisle", "Swamp rats", "Orphans", "river wraith"],
    "silos-keep": ["Lord Silo", "walled", "letters"],
}


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", text))


@pytest.mark.parametrize("location_id", sorted(LOCATIONS))
def test_location_lorebook_shape_and_facts(location_id):
    text = (LORE / f"{location_id}.md").read_text()
    assert text.startswith("# "), "needs an H1 title"
    assert text.count("\n## ") >= 3, "needs at least three sections"
    assert 250 <= words(text) <= 550, f"{words(text)} words"
    for fact in MUST_INCLUDE[location_id]:
        assert fact.lower() in text.lower(), f"{location_id} must mention {fact!r}"


@pytest.mark.parametrize("location_id", sorted(LOCATIONS))
def test_no_spoiler_outside_campaign(location_id):
    text = (LORE / f"{location_id}.md").read_text().lower()
    assert "aldric's master" not in text and "was aldric's" not in text


def test_campaign_md_carries_acts_flags_and_rules():
    text = (LORE / "campaign.md").read_text()
    for heading in ["## Act 1", "## Act 2", "## Act 3", "## Endings", "## Rules for the Dungeon Master"]:
        assert heading in text, heading
    for flag in CANONICAL_FLAGS:
        if flag not in CODE_FLAGS:
            assert f"`{flag}`" in text, f"campaign.md must name {flag}"
    for rule in ["Never reveal", "Offer, never force", "only quotes the player", "earned"]:
        assert rule in text, rule
    for loc in LOCATIONS.values():
        assert loc.name.split(",")[0] in text, loc.name


def test_bestiary_has_new_foes_with_stats():
    text = (LORE / "bestiary.md").read_text()
    for foe in ["Silenced Archivist", "Sealing Warden", "Warden Grisle", "Lord Silo"]:
        assert foe in text, foe
    assert text.count("Hit points") >= 7


def test_no_placeholders_in_content():
    for p in (LORE.parent).rglob("*"):
        if p.is_file() and p.suffix in {".md", ".yaml"}:
            assert not re.search(r"\b(TODO|TBD|FIXME)\b", p.read_text()), p.name


def test_npc_cards_cover_the_cast():
    from rpg.store import load_npc_cards

    cards = {c.npc_id: c for c in load_npc_cards(LORE.parent / "npcs")}
    assert set(cards) == {"marta-quill", "the-sweeper", "keeper-aldric", "ignatia-vale", "the-echo",
                          "odo-brack", "warden-grisle", "lord-silo"}
    for c in cards.values():
        assert c.home_location_id in LOCATIONS
        assert len(c.persona) > 80 and len(c.speech_style) > 30 and len(c.secrets) > 40
    assert "undercroft" in cards["marta-quill"].secrets
    assert "master" in cards["keeper-aldric"].secrets
    assert "letters" in cards["lord-silo"].secrets


# Places the player can see lore from before holding the Lost Catalog (the Swamp and Keep are gated on it).
BEFORE_CATALOG = {"medallion-inn", "delta-crossing", "unity-archive", "spark-forge", "streaming-falls", "photon-mines"}
NPCS = LORE.parent / "npcs"


def test_nothing_seen_before_the_catalog_names_silos_keep():
    # Bible rule: never name Silo's location before has_catalog. campaign.md is the DM's own guide,
    # and its DM rules say as much, so it is the one global book allowed to.
    import yaml

    from_lore = [p for p in LORE.glob("*.md")
                 if p.stem in BEFORE_CATALOG or p.stem not in LOCATIONS and p.stem != "campaign"]
    from_npcs = [p for p in NPCS.glob("*.yaml") if yaml.safe_load(p.read_text())["home_location_id"] in BEFORE_CATALOG]
    leaks = [p.name for p in from_lore + from_npcs if "Silo's Keep" in p.read_text()]
    assert leaks == []


def test_lorebooks_agree_the_archive_was_sealed_a_fortnight_ago():
    assert "fortnight" in (LORE / "unity-archive.md").read_text()
    assert "fortnight" in (LORE / "bestiary.md").read_text()
