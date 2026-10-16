"""Recall what the DM remembers about a player, from the managed memory store (Lakebase-backed)."""

from databricks_agentkit.langgraph.memory import _AGENTS_API, _api
from databricks_agentkit.runtime.tool_manifest import resolve_memory_store

RECALL_QUERY = "the player's past adventures, choices, promises and relationships"


def recall_memories(actor: str, query: str = RECALL_QUERY, limit: int = 5) -> list[str]:
    store = resolve_memory_store(None)
    if not store:
        return []
    data = _api().do("POST", f"{_AGENTS_API}/memory-stores/{store}/entries:search",
                     body={"actor_id": actor, "query": query, "limit": limit})
    return [e.get("content", "") for e in data.get("managed_memory_entries") or [] if e.get("content")]
