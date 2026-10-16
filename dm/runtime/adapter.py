"""Translate between Agent Bricks invocations and the framework-native agent entrypoint."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from agent import agent as agent_module
from agent.agent import recovery_input, run_agent
from langchain.messages import AIMessageChunk
from langgraph.types import Command

from databricks_agentkit import InvocationContext
from databricks_agentkit.langgraph.responses import checkpointed_messages
from databricks_agentkit.langgraph.session_store import thread_config
from databricks_agentkit.runtime.auth import AuthError


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


def _ensure_adventure(payload: dict[str, Any], session_id: str, actor: str) -> None:
    """Create the adventure on new_game (idempotent for replays); otherwise require one to exist."""
    store = agent_module.game_store()
    new_game = _new_game(payload)
    owner = store.owner(session_id)
    if owner is not None and owner != actor:
        raise PermissionError("this adventure belongs to another player")
    if store.load(session_id) is not None:
        return
    if new_game is None:
        raise ValueError("no adventure for this session: send new_game first")
    store.create_adventure(session_id, actor, *new_game)


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


async def _invoke_agent(
    agent_input: Any,
    payload: dict[str, Any],
    context: InvocationContext,
) -> dict:
    session_id = _session_id(context)
    auth = getattr(context, "request_auth", None)
    actor = _player(payload, session_id, auth)
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

    interrupted = bool(outputs and outputs[-1].get("type") == "interrupt")
    return {
        "output": [event["message"] if event["type"] == "message" else event for event in outputs],
        "turn": turn,
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
