"""Recall what the DM remembers about a player, from the managed memory store (Lakebase-backed).

Uses only public agentkit names: the deployed runtime may resolve a different databricks-agentkit
than local dev, and private module internals have changed between versions.
"""

import os

from databricks_agentkit import workspace_client

AGENTS_API = "/api/2.0/agents"
RECALL_QUERY = "the player's past adventures, choices, promises and relationships"


def resolve_memory_store(store: str | None = None) -> str | None:
    """The memory store id: an explicit value, else AGENT_MEMORY_STORE (set by agentbricks deploy)."""
    return store or os.getenv("AGENT_MEMORY_STORE") or None


def _api():
    return workspace_client().api_client


def recall_memories(actor: str, query: str = RECALL_QUERY, limit: int = 5) -> list[str]:
    store = resolve_memory_store()
    if not store:
        return []
    data = _api().do("POST", f"{AGENTS_API}/memory-stores/{store}/entries:search",
                     body={"actor_id": actor, "query": query, "limit": limit})
    return [e.get("content", "") for e in data.get("managed_memory_entries") or [] if e.get("content")]
