"""GameStore contract: every store implementation must pass these."""

import os
import uuid
from pathlib import Path

import pytest
from rpg.state import apply_changes
from rpg.store import InMemoryStore, load_npc_cards

NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        yield InMemoryStore(load_npc_cards(NPCS))
        return
    if not os.getenv("PGHOST"):
        pytest.skip("PGHOST not set; Lakebase contract tests need a live database")
    from agent.pgstore import PostgresStore

    s = PostgresStore.from_env()
    s.seed_npcs(load_npc_cards(NPCS))
    yield s


@pytest.fixture
def sid(store):
    session_id = f"test-{uuid.uuid4()}"
    yield session_id
    store.delete_adventure(session_id)


def test_load_npc_cards():
    cards = load_npc_cards(NPCS)
    assert [c.npc_id for c in cards] == ["ignatia-vale", "keeper-aldric", "lord-silo", "marta-quill", "odo-brack",
                                        "the-echo", "the-sweeper", "warden-grisle"]


def test_create_then_load(store, sid):
    created = store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    loaded = store.load(sid)
    assert loaded == created
    assert loaded.character.name == "Brannoc" and loaded.character.hp == 18
    assert loaded.location_id == "medallion-inn" and loaded.flags == {}
    assert [(n.npc_id, n.disposition) for n in loaded.npcs] == [("marta-quill", 0)]


def test_create_twice_rejected(store, sid):
    store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    with pytest.raises(ValueError):
        store.create_adventure(sid, "player-1", "Other", "bard")


def test_load_unknown_is_none(store):
    assert store.load(f"missing-{uuid.uuid4()}") is None


def test_commit_unknown_session_raises(store):
    game = InMemoryStore(load_npc_cards(NPCS)).create_adventure("x", "p", "A", "bard")
    with pytest.raises(LookupError):
        store.commit(f"missing-{uuid.uuid4()}", game)


def test_commit_persists_all_kinds_of_change(store, sid):
    game = store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    game, _ = apply_changes(game, [
        {"kind": "character", "hp_delta": -4, "gold_delta": -2, "xp_delta": 5, "items_add": ["lantern", "rope"]},
        {"kind": "flag", "flag": "vowed_to_find_aldric", "value": "yes"},
        {"kind": "disposition", "npc_id": "marta-quill", "delta": 1},
        {"kind": "move", "location_id": "delta-crossing"},
    ])
    store.commit(sid, game)
    loaded = store.load(sid)
    c = loaded.character
    assert (c.hp, c.gold, c.xp) == (14, 10, 5)
    assert sorted(c.inventory) == sorted(["longsword (d6+2)", "shield", "rope", "lantern", "rope"])
    assert loaded.flags == {"vowed_to_find_aldric": "yes", "marta_trusts_you": "yes"}
    assert loaded.location_id == "delta-crossing"
    assert [n.npc_id for n in loaded.npcs] == ["the-sweeper"]
    back, _ = apply_changes(loaded, [{"kind": "move", "location_id": "medallion-inn"}])
    store.commit(sid, back)
    assert [(n.npc_id, n.disposition) for n in store.load(sid).npcs] == [("marta-quill", 1)]


def test_list_and_delete(store, sid):
    store.create_adventure(sid, "player-list-test", "Elowen", "mage")
    listed = [a for a in store.list_adventures("player-list-test") if a["session_id"] == sid]
    assert listed == [{"session_id": sid, "name": "Elowen", "archetype": "mage",
                       "location_id": "medallion-inn", "status": "active", "client_session_id": None}]
    store.delete_adventure(sid)
    assert store.load(sid) is None


def test_owner_is_the_creating_player(store, sid):
    assert store.owner(sid) is None
    store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    assert store.owner(sid) == "player-1"


def test_client_session_id_is_stored_and_listed(store, sid):
    store.create_adventure(sid, "player-ref-test", "Brannoc", "warrior", client_session_id="abc-123")
    listed = [a for a in store.list_adventures("player-ref-test") if a["session_id"] == sid]
    assert listed[0]["client_session_id"] == "abc-123"


def test_npc_reveal_after_round_trips(store, sid):
    from rpg.state import NpcCard

    store.seed_npcs([NpcCard(npc_id="test-secretive", name="T", persona="p", speech_style="s", secrets="x",
                             home_location_id="medallion-inn", reveal_after="has_catalog")])
    store.create_adventure(sid, "p", "B", "warrior")
    card = [n for n in store.load(sid).npcs if n.npc_id == "test-secretive"][0]
    assert card.reveal_after == "has_catalog"


def test_stats_start_at_zero_and_add_up(store, sid):
    from rpg.store import STAT_KEYS

    store.create_adventure(sid, "p1", "Tess", "warrior")
    assert store.stats(sid) == {**{k: 0 for k in STAT_KEYS}, "since_start": True}
    store.add_stats(sid, {"lore": 2, "turns": 1})
    store.add_stats(sid, {"lore": 1, "rolls": 1, "turns": 1, "bogus": 9})
    st = store.stats(sid)
    assert (st["lore"], st["rolls"], st["turns"]) == (3, 1, 2) and "bogus" not in st


def test_a_save_from_before_stats_counts_from_now(store, sid):
    store.create_adventure(sid, "p1", "Tess", "warrior")
    if isinstance(store, InMemoryStore):
        store._adventures[sid].pop("stats")  # as if created before M8
    else:
        with store._connect() as conn:
            conn.execute("DELETE FROM rpg.adventure_stats WHERE adventure_id = %s", (sid,))
    assert store.stats(sid) is None
    store.add_stats(sid, {"turns": 1})
    assert store.stats(sid)["turns"] == 1 and store.stats(sid)["since_start"] is False
