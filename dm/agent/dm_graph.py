"""The Dungeon Master turn graph: load_state -> dm_reason <-> tools -> compose.

Each node is a step the curtain panel can light up. The model only writes prose. Dice results
and turn events are built in code from tool results.
"""

import concurrent.futures
import json
from collections.abc import Callable
import logging
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.prompts import COMPOSE_SYSTEM, OPENING_CUE, render_dm_system
from rpg.state import GameState, apply_changes
from rpg.store import GameStore
from rpg.turn import ComposeOutput, TurnEvent, TurnOutput

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS_PER_TURN = 6
HISTORY_TURNS = 8
RECALL_TIMEOUT_S = 5.0  # memory is a bonus; never hold the opening scene hostage to it  # past turns the model sees, besides the current one

FALLBACK_NARRATION = (
    "A strange mist rolls through, and for a moment the world seems to hold its breath. "
    "When it clears, everything is as it was. What do you do?"
)
FALLBACK_CHOICES = ["Look around", "Wait and listen"]

COMMIT_FAILED_NARRATION = (
    "The world shimmers and slips, like a page turned too quickly. Nothing you just did seems "
    "to have stuck. What do you do?"
)


def _stage(left: list | None, right: list | None) -> list:
    """Reducer for staged changes: None resets (start of turn), a list appends."""
    return [] if right is None else [*(left or []), *right]


class DMState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    character: dict
    location_id: str
    flags: dict
    npcs: list[dict]
    staged: Annotated[list[dict], _stage]
    state_summaries: list[str]
    commit_failed: bool
    turn: dict | None
    reason_failed: bool
    memories: list[str]
    memories_new: bool


def _game(state: DMState) -> GameState:
    return GameState(character=state["character"], location_id=state["location_id"],
                     flags=state.get("flags") or {}, npcs=state.get("npcs") or [])


def _game_update(game: GameState) -> dict:
    return {"character": game.character.model_dump(), "location_id": game.location_id,
            "flags": dict(game.flags), "npcs": [n.model_dump() for n in game.npcs]}


def _current_turn(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Messages since (and including) the latest player message."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i:]
    return list(messages)


def _tool_calls_used(messages: list[AnyMessage]) -> int:
    return sum(isinstance(m, ToolMessage) for m in _current_turn(messages))


def _tool_result(message: ToolMessage) -> dict | None:
    try:
        value = json.loads(message.content) if isinstance(message.content, str) else message.content
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _roll_event(r: dict) -> TurnEvent:
    verdict = "success" if r["success"] else "failure"
    summary = (
        f"{r['stat'].title()} check: {r['roll']} {r['modifier']:+d} = {r['total']} "
        f"vs DC {r['dc']}, {verdict}"
    )
    return TurnEvent(type="roll", summary=summary, detail=r)


def _lore_event(r: dict) -> TurnEvent:
    passages = r.get("passages", [])
    sources = ", ".join(dict.fromkeys(p["source"] for p in passages)) or "nothing found"
    summary = f"Lore: {len(passages)} passages for '{r['query']}' ({sources})"
    return TurnEvent(type="lore", summary=summary, detail=r)


def _attack_event(r: dict) -> TurnEvent:
    who = f"{r['attacker']} attacks {r['target']}" if "attacker" in r else f"Attack on {r['target']}"
    outcome = f"hit for {r['damage']}" if r["hit"] else "miss"
    summary = f"{who}: {r['roll']} {r['modifier']:+d} = {r['total']} vs defence {r['defence']}, {outcome}"
    return TurnEvent(type="attack", summary=summary, detail=r)


def _memory_event(r: dict) -> TurnEvent:
    return TurnEvent(type="memory", summary="Memory: " + str(r.get("result", r))[:120], detail=r)


_EVENT_BUILDERS = {"roll_check": _roll_event, "search_lore": _lore_event,
                   "resolve_attack": _attack_event, "enemy_attack": _attack_event,
                   "remember": _memory_event, "recall": _memory_event}


def turn_events(messages: list[AnyMessage]) -> list[TurnEvent]:
    """Build curtain events in code from this turn's successful tool results."""
    events = []
    for m in _current_turn(messages):
        build = _EVENT_BUILDERS.get(getattr(m, "name", None)) if isinstance(m, ToolMessage) else None
        if build is None or getattr(m, "status", "success") == "error":
            continue
        r = _tool_result(m)
        if r is None and build is _memory_event:  # memory tools return plain text
            r = {"result": m.content}
        if r and "error" not in r:
            events.append(build(r))
    return events


def _sendable(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Drop a trailing AI message whose tool calls were never answered (budget exhausted)."""
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return messages[:-1]
    return messages


def _context(messages: list[AnyMessage]) -> list[AnyMessage]:
    """What the model sees: the current turn in full plus the last HISTORY_TURNS past turns.

    Past turns are already compacted to player message + narration (see compose), so this
    keeps every model call a bounded size however long the adventure runs.
    """
    starts = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(starts) > HISTORY_TURNS + 1:
        messages = messages[starts[-(HISTORY_TURNS + 1)]:]
    return _sendable(messages)


def compose_turn(
    llm: Any,
    messages: list[AnyMessage],
    location_id: str,
    events: list[TurnEvent],
    previous_choices: list[str] | None,
    applied: list[str] | None = None,
) -> TurnOutput:
    structured = llm.with_structured_output(ComposeOutput)
    system = COMPOSE_SYSTEM
    if applied:
        system += (
            "\n\nState changes applied this turn (narrate consistently with these; if the player was "
            f"downed they collapse and wake at the Medallion Inn): {'; '.join(applied)}"
        )
    prompt = [SystemMessage(system), *_context(messages)]
    for _ in range(2):  # one attempt plus one repair retry
        try:
            result = structured.invoke(prompt)
            prose = result if isinstance(result, ComposeOutput) else ComposeOutput.model_validate(result)
            return TurnOutput.from_compose(prose, location_id, events)
        except Exception:  # noqa: BLE001 - any model/parse failure falls through to retry/fallback
            logger.warning("compose attempt failed", exc_info=True)
    return fallback_turn(location_id, events, previous_choices)


def fallback_turn(
    location_id: str, events: list[TurnEvent], previous_choices: list[str] | None
) -> TurnOutput:
    fallback = ComposeOutput(narration=FALLBACK_NARRATION, choices=previous_choices or FALLBACK_CHOICES)
    return TurnOutput.from_compose(fallback, location_id, events)


def build_dm_graph(llm: Any, tools: list[BaseTool], checkpointer: Any = None, *, store: GameStore,
                   recall: Callable[[str], list[str]] | None = None):
    reasoner = llm.bind_tools(tools)

    def _sid(config: RunnableConfig) -> str:
        return config["configurable"]["thread_id"]

    def load_state(state: DMState, config: RunnableConfig) -> dict:
        actor = config["configurable"].get("actor_id")
        if actor is not None and store.owner(_sid(config)) not in (None, actor):
            raise PermissionError("this adventure belongs to another player")
        game = store.load(_sid(config))
        if game is None:
            raise LookupError(f"no adventure for session {_sid(config)}")
        update = {**_game_update(game), "staged": None, "state_summaries": [], "commit_failed": False}
        messages = state.get("messages") or []
        if not messages or not isinstance(messages[-1], HumanMessage):
            update["messages"] = [HumanMessage(OPENING_CUE)]
        if recall is not None and "memories" not in state:
            try:
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = pool.submit(recall, config["configurable"].get("actor_id") or _sid(config))
                pool.shutdown(wait=False)  # a slow recall finishes in the background, unused
                memories = future.result(timeout=RECALL_TIMEOUT_S)
            except Exception:  # noqa: BLE001 - memory is a bonus; never break the turn
                logger.warning("memory recall failed", exc_info=True)
                memories = []
            update["memories"] = memories
            update["memories_new"] = bool(memories)
        else:
            update["memories_new"] = False
        return update

    def dm_reason(state: DMState) -> dict:
        system = SystemMessage(render_dm_system(_game(state), state.get("memories") or []))
        try:
            return {"messages": [reasoner.invoke([system, *_context(state["messages"])])]}
        except Exception:  # noqa: BLE001 - the world never breaks character; compose falls back
            logger.warning("dm_reason model call failed", exc_info=True)
            return {"reason_failed": True}

    def route(state: DMState) -> str:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        if calls and _tool_calls_used(state["messages"]) + len(calls) <= MAX_TOOL_CALLS_PER_TURN:
            return "tools"
        return "commit_state"

    def commit_state(state: DMState, config: RunnableConfig) -> dict:
        staged = state.get("staged") or []
        if not staged or state.get("reason_failed"):  # an aborted turn commits nothing
            return {}
        try:
            new, summaries = apply_changes(_game(state), staged)
            store.commit(_sid(config), new)
        except Exception:  # noqa: BLE001 - rolled back by the store; the turn reports failure in-world
            logger.warning("commit_state failed", exc_info=True)
            return {"commit_failed": True}
        try:
            game = store.load(_sid(config))  # authoritative, and refreshes who is here after a move
        except Exception:  # noqa: BLE001 - the commit landed; fall back to the state we just wrote
            logger.warning("reload after commit failed", exc_info=True)
            game = new
        return {**_game_update(game), "state_summaries": summaries}

    def compose(state: DMState) -> dict:
        messages = state["messages"]
        previous = (state.get("turn") or {}).get("choices")
        events = turn_events(messages)
        if state.get("commit_failed") or state.get("reason_failed"):
            turn = fallback_turn(state["location_id"], [], previous)
            if state.get("commit_failed"):
                turn.narration = COMMIT_FAILED_NARRATION
            removals = [RemoveMessage(id=m.id) for m in _current_turn(messages)
                        if not isinstance(m, HumanMessage)]
        else:
            if state.get("memories_new"):
                n = len(state["memories"])
                events.insert(0, TurnEvent(type="memory", summary=f"Memory: recalled {n} thing{'s' if n != 1 else ''} about you",
                                           detail={"memories": state["memories"]}))
            if state.get("state_summaries"):
                events.append(TurnEvent(type="state", summary="; ".join(state["state_summaries"]),
                                        detail={"changes": state.get("staged") or []}))
            turn = compose_turn(llm, messages, state["location_id"], events, previous,
                                applied=state.get("state_summaries"))
            # Compact the finished turn: drop dm_reason's draft prose and every tool call and result
            # (calls and results go together, so history stays provider-valid). The trace keeps them.
            removals = [
                RemoveMessage(id=m.id) for m in _current_turn(messages)
                if isinstance(m, ToolMessage) or (isinstance(m, AIMessage) and (m.tool_calls or m is messages[-1]))
            ]
        text = turn.narration + "\n\n" + "\n".join(f"- {c}" for c in turn.choices)
        return {"turn": turn.model_dump(), "messages": [*removals, AIMessage(content=text)],
                "reason_failed": False, "commit_failed": False}

    builder = StateGraph(DMState)
    builder.add_node("load_state", load_state)
    builder.add_node("dm_reason", dm_reason)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_node("commit_state", commit_state)
    builder.add_node("compose", compose)
    builder.add_edge(START, "load_state")
    builder.add_edge("load_state", "dm_reason")
    builder.add_conditional_edges("dm_reason", route, {"tools": "tools", "commit_state": "commit_state"})
    builder.add_edge("tools", "dm_reason")
    builder.add_edge("commit_state", "compose")
    builder.add_edge("compose", END)
    return builder.compile(checkpointer=checkpointer)
