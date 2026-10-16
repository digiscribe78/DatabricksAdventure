from types import SimpleNamespace

import agent.memory as memory


def test_no_store_configured_returns_nothing(monkeypatch):
    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: None)
    assert memory.recall_memories("p1") == []


def test_recall_searches_actor_partition(monkeypatch):
    calls = []

    class Api:
        def do(self, method, path, body):
            calls.append((method, path, body))
            return {"managed_memory_entries": [{"content": "Spared the thief"}, {"content": "Owes Marta a story"}]}

    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: "mem-1")
    monkeypatch.setattr(memory, "_api", lambda: Api())
    assert memory.recall_memories("p1", limit=2) == ["Spared the thief", "Owes Marta a story"]
    method, path, body = calls[0]
    assert method == "POST" and path.endswith("/memory-stores/mem-1/entries:search")
    assert body == {"actor_id": "p1", "query": memory.RECALL_QUERY, "limit": 2}
