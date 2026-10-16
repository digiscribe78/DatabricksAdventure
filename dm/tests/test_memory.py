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


def test_memory_module_uses_only_public_agentkit_names():
    # The deployed runtime may resolve a different databricks-agentkit; private names broke a deploy.
    import inspect

    src = inspect.getsource(memory)
    assert "databricks_agentkit.langgraph.memory" not in src
    assert "tool_manifest" not in src


def test_store_resolves_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_STORE", "mem-env")
    assert memory.resolve_memory_store() == "mem-env"
    monkeypatch.delenv("AGENT_MEMORY_STORE")
    assert memory.resolve_memory_store() is None
