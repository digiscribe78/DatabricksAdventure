from types import SimpleNamespace

import agent.memory as memory


def test_no_store_configured_returns_nothing(monkeypatch):
    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: None)
    assert memory.recall_memories("p1") == []


def test_recall_searches_actor_partition(monkeypatch):
    calls = []

    def hit(text):
        return SimpleNamespace(memory=SimpleNamespace(content=text), score=0.5)

    class Store:
        def search(self, *, actor_id, query, limit):
            calls.append((actor_id, query, limit))
            return [hit("Spared the thief"), hit("Owes Marta a story"), hit("")]

    class Stores:
        def get(self, name):
            calls.append(("get", name))
            return Store()

    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: "mem-1")
    monkeypatch.setattr(memory, "_client", lambda: SimpleNamespace(memory_stores=Stores()))
    assert memory.recall_memories("p1", limit=2) == ["Spared the thief", "Owes Marta a story"]
    assert calls == [("get", "mem-1"), ("p1", memory.RECALL_QUERY, 2)]


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
