"""Turn transcripts for long-term memory, in a session store the Dreamer pipeline can read.

The LangGraph checkpointer's session store holds msgpack checkpoint blobs, which the memory
pipeline can't distil. Per the platform tutorial for LangGraph agents, each turn is also written
here as plain user/assistant messages, under the same actor and session as the checkpointer.
"""

import logging
import os
import tomllib
from pathlib import Path

from agent.memory import resolve_memory_store

logger = logging.getLogger(__name__)

AGENT_TOML = Path(__file__).resolve().parents[1] / "agent.toml"
# The Dreamer instructions: the repo's content/ in dev, copied next to agent.toml in the deploy build.
_INSTRUCTIONS = (Path(__file__).resolve().parents[2] / "content" / "dreamer-instructions.md",
                 Path(__file__).resolve().parents[1] / "dreamer-instructions.md")


def transcript_store_name(toml_path: Path = AGENT_TOML) -> str:
    name = tomllib.loads(toml_path.read_text())["session_store"]["name"]
    return name.removesuffix("-sessions") + "-transcripts"


def dreamer_instructions() -> str | None:
    for path in _INSTRUCTIONS:
        if path.is_file():
            return path.read_text()
    return None


def _client(client):
    if client is not None:
        return client
    from databricks_agentkit import AgentKitClient, workspace_client

    return AgentKitClient(workspace_client())


def _session(client, actor: str, session_id: str, *, create: bool):
    store = client.session_stores.get(os.environ["TRANSCRIPT_STORE"])
    try:
        return store.get(session_id)
    except Exception:  # noqa: BLE001 - not found on a session's first turn
        if not create:
            raise
        return store.add(actor_id=actor, session_id=session_id)


def record_turn(actor: str, session_id: str, player_text: str | None, reply: str, invocation_id: str | None,
                client=None) -> None:
    """Append this turn as plain messages. Never raises: memory is a bonus, the turn is not."""
    if not os.getenv("TRANSCRIPT_STORE"):
        return
    try:
        session = _session(_client(client), actor, session_id, create=True)
        latest = next(iter(session.list_items(page_size=1, order_by="create_time desc")), None)
        if invocation_id and latest is not None and (latest.data or {}).get("invocation_id") == invocation_id:
            return  # a recovery replay of a turn already recorded
        items = [{"type": "message", "role": "user", "content": player_text, "invocation_id": invocation_id}
                 ] if player_text else []
        items.append({"type": "message", "role": "assistant", "content": reply, "invocation_id": invocation_id})
        session.append_items(items)
    except Exception:  # noqa: BLE001 - never break the turn
        logger.warning("recording the transcript failed", exc_info=True)


def distil_adventure(actor: str, session_id: str, client=None) -> list[str]:
    """Distil a finished adventure into long-term memories now; returns what was learned."""
    memory_store = resolve_memory_store()
    if not os.getenv("TRANSCRIPT_STORE") or not memory_store:
        return []
    try:
        session = _session(_client(client), actor, session_id, create=False)
        entries = session.extract_memories(memory_store=memory_store, instructions=dreamer_instructions())
        return [e.content for e in entries if getattr(e, "content", None)]
    except Exception:  # noqa: BLE001 - never break the final turn
        logger.warning("distilling the adventure failed", exc_info=True)
        return []
