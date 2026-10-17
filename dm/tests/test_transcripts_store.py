from types import SimpleNamespace

from devtools.memory_pipeline import plan
from devtools.transcripts_store import ensure_store, grant_store


class Stores:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []
        self.granted = []

    def get(self, name):
        if name not in self.existing:
            raise RuntimeError("NOT_FOUND")
        return SimpleNamespace(grant_permission=lambda sp, permission="WRITE": self.granted.append((name, sp, permission)))

    def create(self, name, *, description=None, metadata=None):
        self.created.append(name)
        self.existing.add(name)


def test_missing_store_is_created_and_existing_left_alone():
    stores = Stores()
    client = SimpleNamespace(session_stores=stores)
    assert ensure_store(client, "dm-x-transcripts") is True
    assert ensure_store(client, "dm-x-transcripts") is False
    assert stores.created == ["dm-x-transcripts"]


def test_the_dm_gets_write_on_the_store():
    stores = Stores(["dm-x-transcripts"])
    grant_store(SimpleNamespace(session_stores=stores), "dm-x-transcripts", "sp-1")
    assert stores.granted == [("dm-x-transcripts", "sp-1", "WRITE")]


def pipe(name, sessions, memory="memory-stores/dm-x-memory", display="dm-dreamer"):
    return {"name": name, "display_name": display, "session_store": f"session-stores/{sessions}", "memory_store": memory}


def test_a_dreamer_on_the_checkpoint_store_is_replaced():
    delete, create = plan([pipe("memory-pipelines/a", "dm-x-sessions")], "dm-x-memory", "dm-x-transcripts")
    assert delete == ["memory-pipelines/a"] and create is True


def test_a_dreamer_on_the_transcripts_is_kept():
    delete, create = plan([pipe("memory-pipelines/b", "dm-x-transcripts")], "dm-x-memory", "dm-x-transcripts")
    assert delete == [] and create is False


def test_other_pipelines_are_not_touched():
    other = pipe("memory-pipelines/c", "someone-sessions", memory="memory-stores/other", display="their-dreamer")
    delete, create = plan([other], "dm-x-memory", "dm-x-transcripts")
    assert delete == [] and create is True
