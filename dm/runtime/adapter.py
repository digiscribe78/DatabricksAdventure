"""Translate between Agent Bricks invocations and the framework-native agent entrypoint."""

import asyncio
import logging
import os
import re

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from agent import agent as agent_module
from agent.guardrails import REFUSED_PLACEHOLDER
from agent.transcripts import distil_adventure, record_turn
from agent.agent import recovery_input, run_agent
from langchain.messages import AIMessageChunk
from langgraph.types import Command

from databricks_agentkit import InvocationContext
from databricks_agentkit.langgraph.responses import checkpointed_messages
from databricks_agentkit.langgraph.session_store import thread_config
from databricks_agentkit.runtime.auth import AuthError
from rpg.hints import next_hint
from rpg.store import STAT_KEYS
from rpg.world import LOCATIONS


logger = logging.getLogger(__name__)

def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"messages": value}
    if not isinstance(value, dict):
        raise ValueError("input must be a message list or an object")
    return value


def _session_id(context: InvocationContext) -> str:
    value = context.session_id
    if not isinstance(value, str) or not value:
        raise ValueError("session_id must be provided as a top-level invocation field")
    return value


def _actor(payload: dict[str, Any], session_id: str) -> str:
    value = payload.get("actor") or session_id
    if not isinstance(value, str) or not value:
        raise ValueError("actor must be a non-empty string")
    return value


def _player(payload: dict[str, Any], session_id: str, auth: Any) -> str:
    """Who is playing: the authenticated principal when deployed, never a client-supplied value."""
    if auth is not None:
        return auth.namespace("player", "self")
    return _actor(payload, session_id)


def _agent_input(payload: dict[str, Any]) -> Any:
    if (resume := payload.get("resume")) is not None:
        return Command(resume=resume)
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    # Trust boundary: players may only speak as the user. System, assistant and tool messages,
    # and message ids (which would overwrite history), are never accepted from clients.
    cleaned = []
    for m in messages:
        if not (isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)):
            raise ValueError("only user messages with string content are accepted")
        cleaned.append({"role": "user", "content": m["content"]})
    return {"messages": cleaned}


def _new_game(payload: dict[str, Any]) -> tuple[str, str] | None:
    ng = payload.get("new_game")
    if ng is None:
        return None
    from rpg.world import ARCHETYPES

    name = ng.get("name") if isinstance(ng, dict) else None
    archetype = ng.get("archetype") if isinstance(ng, dict) else None
    if not (isinstance(name, str) and 1 <= len(name.strip()) <= 40):
        raise ValueError("new_game.name must be 1-40 characters")
    if archetype not in ARCHETYPES:
        raise ValueError(f"new_game.archetype must be one of {sorted(ARCHETYPES)}")
    return name.strip(), archetype


_CLIENT_REF = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _client_session_id(payload: dict[str, Any]) -> str | None:
    ref = payload.get("client_session_id")
    if ref is None:
        return None
    if not (isinstance(ref, str) and _CLIENT_REF.fullmatch(ref)):
        raise ValueError("client_session_id must be 1-64 letters, digits or hyphens")
    return ref


def _hint(game) -> dict | None:
    try:
        return next_hint(dict(game.flags), game.location_id)
    except Exception:  # noqa: BLE001 - a broken hints file costs the hint, never the turn
        logger.warning("working out the hint failed", exc_info=True)
        return None


def game_snapshot(game) -> dict:
    """What the browser may see: no NPC secrets, no lore, no drafts."""
    here = LOCATIONS[game.location_id]
    host = os.getenv("DATABRICKS_HOST", "").removeprefix("https://").rstrip("/")
    exp = os.getenv("MLFLOW_EXPERIMENT_ID")
    return {
        "character": game.character.model_dump(),
        "location_id": game.location_id,
        "location_name": here.name,
        "exits": [{"id": e, "name": LOCATIONS[e].name, "open": here.barrier(e, game.flags) is None}
                  for e in here.exits if e in LOCATIONS],
        "flags": dict(game.flags),
        "npcs": [{"npc_id": n.npc_id, "name": n.name, "disposition": n.disposition} for n in game.npcs],
        "traces_url": f"https://{host}/ml/experiments/{exp}/traces" if host and exp else None,
        "hint": _hint(game),
    }


def _ensure_adventure(payload: dict[str, Any], session_id: str, actor: str) -> None:
    """Create the adventure on new_game (idempotent for replays); otherwise require one to exist."""
    store = agent_module.game_store()
    new_game = _new_game(payload)
    client_ref = _client_session_id(payload)
    owner = store.owner(session_id)
    if owner is not None and owner != actor:
        raise PermissionError("this adventure belongs to another player")
    if store.load(session_id) is not None:
        return
    if new_game is None:
        raise ValueError("no adventure for this session: send new_game first")
    store.create_adventure(session_id, actor, *new_game, client_session_id=client_ref)


async def invoke(value: Any, context: InvocationContext) -> dict:
    payload = _payload(value)
    _check_user_input(payload, context)
    return await _invoke_agent(_agent_input(payload), payload, context)


async def recover(value: Any, context: InvocationContext) -> dict:
    payload = _payload(value)
    _check_user_input(payload, context)
    if getattr(context, "request_auth", None) is not None:
        raise AuthError(
            "MCP_USER_AUTH_BACKGROUND_UNSUPPORTED",
            "Request-user invocations cannot be recovered in the background.",
            400,
        )
    session_id = _session_id(context)
    actor = _actor(payload, session_id)
    agent_input = await recovery_input(
        _agent_input(payload),
        session_id=session_id,
        actor=actor,
        invocation_id=context.invocation_id,
    )
    return await _invoke_agent(agent_input, payload, context)


def _check_user_input(payload: dict[str, Any], context: InvocationContext) -> None:
    auth = getattr(context, "request_auth", None)
    if auth is not None and any(
        payload.get(key) is not None for key in ("resume", "approval", "approvals")
    ):
        raise AuthError(
            "MCP_USER_AUTH_HITL_UNSUPPORTED",
            "Request-user invocations do not support approval or resume input.",
            400,
        )


_EVENT_STATS = {"roll": "rolls", "attack": "attacks", "lore": "lore", "memory": "memories",
                "state": "state_commits", "guardrail": "guardrails"}


def turn_counts(turn: dict, hints_seen: Any) -> dict[str, int]:
    """This turn's contribution to the adventure's "what you just saw" counts."""
    counts = dict.fromkeys(STAT_KEYS, 0)
    for e in turn.get("events") or []:
        if (key := _EVENT_STATS.get(e.get("type"))) is not None:
            counts[key] += 1
    ok = isinstance(hints_seen, int) and not isinstance(hints_seen, bool) and 0 <= hints_seen <= 20
    counts["hints"] = hints_seen if ok else 0
    counts["turns"] = 1
    return counts


_UNREAD = object()  # the stats read failed, as opposed to there being no row yet


def _read_stats(session_id: str):
    try:
        return agent_module.game_store().stats(session_id)
    except Exception:  # noqa: BLE001 - the end-screen counts are a bonus, the turn is not
        logger.warning("reading adventure stats failed", exc_info=True)
        return _UNREAD


def _add_stats(session_id: str, counts: dict[str, int]) -> None:
    try:
        agent_module.game_store().add_stats(session_id, counts)
    except Exception:  # noqa: BLE001 - stats never break the turn
        logger.warning("recording adventure stats failed", exc_info=True)


DISTIL_TIMEOUT_S = 20.0  # the ending never waits longer than this for the platform to distil it


async def _distil(actor: str, session_id: str) -> list[str]:
    try:
        return await asyncio.wait_for(asyncio.to_thread(distil_adventure, actor, session_id), DISTIL_TIMEOUT_S)
    except TimeoutError:
        return []  # the next Dreamer run distils it instead


def turn_transcript(agent_input: Any, turn: dict) -> tuple[str | None, str]:
    """What the transcript records for a turn: the player's words (or the placeholder) and the reply."""
    messages = agent_input.get("messages") if isinstance(agent_input, dict) else None
    users = [m.get("content") for m in messages or [] if isinstance(m, dict) and m.get("role") == "user"]
    player = users[-1] if users and isinstance(users[-1], str) and users[-1].strip() else None
    if player is not None and any(e.get("type") == "guardrail" for e in turn.get("events") or []):
        player = REFUSED_PLACEHOLDER  # blocked words never reach the transcript or memory
    choices = "\n".join(f"- {c}" for c in turn.get("choices") or [])
    reply = (turn.get("narration") or "") + (f"\n\n{choices}" if choices else "")
    return player, reply


async def _invoke_agent(
    agent_input: Any,
    payload: dict[str, Any],
    context: InvocationContext,
) -> dict:
    session_id = _session_id(context)
    auth = getattr(context, "request_auth", None)
    actor = _player(payload, session_id, auth)
    if payload.get("list_adventures") is True:
        return {"adventures": agent_module.game_store().list_adventures(actor), "status": "completed"}
    _ensure_adventure(payload, session_id, actor)
    user_auth = auth is not None
    run_kwargs = {"workspace_client_for": auth.client_for} if user_auth else {}
    model = payload.get("model")
    model = model if isinstance(model, str) else None
    outputs = []
    if agent_input is None:
        graph = await agent_module.create_agent_graph(actor, model, **run_kwargs)
        outputs = [
            {"type": "message", "message": message.model_dump()}
            for message in await checkpointed_messages(
                graph, thread_config(session_id, actor), context.invocation_id
            )
        ]
        run_kwargs["graph"] = graph
    turn = None
    async for event in _serialize_events(
        run_agent(
            agent_input,
            session_id=session_id,
            actor=actor,
            model=model,
            invocation_id=context.invocation_id,
            **run_kwargs,
        )
    ):
        if user_auth and event.get("type") == "interrupt":
            raise AuthError(
                "MCP_USER_AUTH_HITL_UNSUPPORTED",
                "Request-user invocations do not support paused approvals.",
                400,
            )
        await context.emit(event)
        if event.get("type") == "turn":
            turn = event["turn"]
        if event.get("type") in ("message", "interrupt"):
            outputs.append(event)

    game = agent_module.game_store().load(session_id)
    snapshot = game_snapshot(game) if game is not None else None
    counts = turn_counts(turn, payload.get("hints_seen")) if turn is not None else None
    if snapshot is not None:
        stats = _read_stats(session_id)
        if stats is _UNREAD:
            stats = None
        elif stats is not None and counts is not None:
            stats = {k: (v + counts.get(k, 0) if k in counts else v) for k, v in stats.items()}  # include this turn
        elif counts is not None:
            stats = {**counts, "since_start": False}  # a save from before stats: its row is created below
        snapshot["stats"] = stats
        await context.emit({"type": "game", "game": snapshot})
    if turn is not None:
        # After the player has the new state: blocking calls, so off the event loop.
        await asyncio.to_thread(_add_stats, session_id, counts)
        await asyncio.to_thread(record_turn, actor, session_id, *turn_transcript(agent_input, turn),
                                context.invocation_id)
        if snapshot is not None and turn.get("game_over"):
            snapshot["distilled"] = await _distil(actor, session_id)  # after the ending is recorded
            await context.emit({"type": "game", "game": snapshot})
    interrupted = bool(outputs and outputs[-1].get("type") == "interrupt")
    return {
        "output": [event["message"] if event["type"] == "message" else event for event in outputs],
        "turn": turn,
        "game": snapshot,
        "status": "interrupted" if interrupted else "completed",
    }


async def _serialize_events(async_stream: AsyncIterator[Any]) -> AsyncGenerator[dict, None]:
    async for mode, payload in async_stream:
        if mode == "updates":
            if interrupts := payload.get("__interrupt__"):
                for item in interrupts:
                    yield {"type": "interrupt", "id": item.id, "value": item.value}
                continue
            for node_name, node_data in payload.items():
                yield {"type": "node", "node": node_name}
                if not isinstance(node_data, dict):
                    continue
                for message in node_data.get("messages", []):
                    yield {"type": "message", "message": message.model_dump()}
                if node_data.get("turn") is not None:
                    yield {"type": "turn", "turn": node_data["turn"]}
        elif mode == "messages":
            try:
                chunk = payload[0]
                if isinstance(chunk, AIMessageChunk) and (content := chunk.content):
                    yield {"type": "delta", "content": content, "id": chunk.id}
            except (KeyError, IndexError, TypeError):
                continue
