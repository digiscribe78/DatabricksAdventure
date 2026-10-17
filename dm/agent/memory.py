"""Recall what the DM remembers about a player, from the managed memory store (Lakebase-backed).

Uses the public AgentKit SDK (`AgentKitClient`), as the platform's memory tutorial does: the deployed
runtime may resolve a different databricks-agentkit than local dev, so no private module internals.
"""

import os

from databricks_agentkit import workspace_client

RECALL_QUERY = "the player's past adventures, choices, promises and relationships"


def resolve_memory_store(store: str | None = None) -> str | None:
    """The memory store id: an explicit value, else AGENT_MEMORY_STORE (set by agentbricks deploy)."""
    return store or os.getenv("AGENT_MEMORY_STORE") or None


def _client():
    from databricks_agentkit import AgentKitClient

    return AgentKitClient(workspace_client())


def recall_memories(actor: str, query: str = RECALL_QUERY, limit: int = 5) -> list[str]:
    store = resolve_memory_store()
    if not store:
        return []
    results = _client().memory_stores.get(store).search(actor_id=actor, query=query, limit=limit)
    return [r.memory.content for r in results if getattr(r.memory, "content", None)]
