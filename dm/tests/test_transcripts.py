from pathlib import Path

import agent.transcripts as transcripts
import pytest


class FakeSession:
    def __init__(self):
        self.items = []
        self.extract_calls = []

    def list_items(self, *, page_size=None, order_by=None):
        items = list(reversed(self.items)) if order_by == "create_time desc" else list(self.items)
        return iter([type("Item", (), {"data": d})() for d in items[:page_size or len(items)]])

    def append_items(self, items):
        self.items.extend(items)
        return items

    def extract_memories(self, *, memory_store, instructions=None, dry_run=False):
        self.extract_calls.append((memory_store, instructions))
        entry = type("Entry", (), {"content": "Spared the river wraith"})()
        return [entry]


class FakeStore:
    def __init__(self):
        self.sessions = {}
        self.added = []

    def get(self, session_id):
        if session_id not in self.sessions:
            raise RuntimeError("NOT_FOUND: Session not found")
        return self.sessions[session_id]

    def add(self, *, actor_id, session_id=None, parent_session_id=None, metadata=None):
        self.added.append((actor_id, session_id))
        self.sessions[session_id] = FakeSession()
        return self.sessions[session_id]


class FakeClient:
    def __init__(self):
        self.store = FakeStore()
        self.session_stores = type("S", (), {"get": lambda _self, name: self.store})()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("TRANSCRIPT_STORE", "dm-x-transcripts")
    monkeypatch.setenv("AGENT_MEMORY_STORE", "dm-x-memory")


def test_store_name_is_derived_from_the_checkpointer_store(tmp_path):
    toml = tmp_path / "agent.toml"
    toml.write_text('[session_store]\nname = "dm-abc-sessions"\n')
    assert transcripts.transcript_store_name(toml) == "dm-abc-transcripts"


def test_first_turn_adds_the_session_and_writes_plain_messages(env):
    client = FakeClient()
    transcripts.record_turn("p1", "s1", "I bow to Marta.", "Marta smiles.\n\n- Ask\n- Leave", "inv-1", client=client)
    assert client.store.added == [("p1", "s1")]
    assert client.store.sessions["s1"].items == [
        {"type": "message", "role": "user", "content": "I bow to Marta.", "invocation_id": "inv-1"},
        {"type": "message", "role": "assistant", "content": "Marta smiles.\n\n- Ask\n- Leave", "invocation_id": "inv-1"},
    ]


def test_later_turns_reuse_the_session(env):
    client = FakeClient()
    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=client)
    transcripts.record_turn("p1", "s1", "c", "d", "inv-2", client=client)
    assert client.store.added == [("p1", "s1")] and len(client.store.sessions["s1"].items) == 4


def test_cue_turns_record_only_the_reply(env):
    client = FakeClient()
    transcripts.record_turn("p1", "s1", None, "The adventure begins.", "inv-1", client=client)
    assert [i["role"] for i in client.store.sessions["s1"].items] == ["assistant"]


def test_a_replayed_invocation_is_recorded_once(env):
    client = FakeClient()
    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=client)
    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=client)
    assert len(client.store.sessions["s1"].items) == 2


def test_failures_never_break_the_turn(env):
    class Broken:
        @property
        def session_stores(self):
            raise ConnectionError("down")

    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=Broken())  # no raise
    assert transcripts.distil_adventure("p1", "s1", client=Broken()) == []


def test_unconfigured_store_is_a_no_op(monkeypatch):
    monkeypatch.delenv("TRANSCRIPT_STORE", raising=False)
    client = FakeClient()
    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=client)
    assert client.store.added == []
    assert transcripts.distil_adventure("p1", "s1", client=client) == []


def test_distil_extracts_into_the_memory_store_with_the_dreamer_instructions(env):
    client = FakeClient()
    transcripts.record_turn("p1", "s1", "a", "b", "inv-1", client=client)
    assert transcripts.distil_adventure("p1", "s1", client=client) == ["Spared the river wraith"]
    [(store, instructions)] = client.store.sessions["s1"].extract_calls
    assert store == "dm-x-memory" and "Kingdom of Sparkia" in instructions


def test_dreamer_instructions_come_from_content_in_dev():
    assert transcripts.dreamer_instructions().startswith("You are distilling")
