"""The Dungeon Master turn graph: load_state -> dm_reason <-> tools -> compose.

Each node is a step the curtain panel can light up. The model only writes prose. Dice results
and turn events are built in code from tool results.
"""

import json
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.prompts import COMPOSE_SYSTEM, OPENING_CUE, render_dm_system
from rpg.turn import ComposeOutput, TurnEvent, TurnOutput
from rpg.world import DEFAULT_CHARACTER, LOCATIONS, START_LOCATION_ID, Character

MAX_TOOL_CALLS_PER_TURN = 6

FALLBACK_NARRATION = (
    "A strange mist rolls through, and for a moment the world seems to hold its breath. "
    "When it clears, everything is as it was. What do you do?"
)
FALLBACK_CHOICES = ["Look around", "Wait and listen"]


class DMState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    character: dict
    location_id: str
    turn: dict | None


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


def roll_events(messages: list[AnyMessage]) -> list[TurnEvent]:
    events = []
    for m in _current_turn(messages):
        if not (isinstance(m, ToolMessage) and m.name == "roll_check"):
            continue
        r = _tool_result(m)
        if not r or "error" in r:
            continue
        verdict = "success" if r["success"] else "failure"
        summary = (
            f"{r['stat'].title()} check: {r['roll']} {r['modifier']:+d} = {r['total']} "
            f"vs DC {r['dc']}, {verdict}"
        )
        events.append(TurnEvent(type="roll", summary=summary, detail=r))
    return events


def _sendable(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Drop a trailing AI message whose tool calls were never answered (budget exhausted)."""
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return messages[:-1]
    return messages


def compose_turn(
    llm: Any,
    messages: list[AnyMessage],
    location_id: str,
    events: list[TurnEvent],
    previous_choices: list[str] | None,
) -> TurnOutput:
    structured = llm.with_structured_output(ComposeOutput)
    prompt = [SystemMessage(COMPOSE_SYSTEM), *_sendable(messages)]
    for _ in range(2):  # one attempt plus one repair retry
        try:
            result = structured.invoke(prompt)
            prose = result if isinstance(result, ComposeOutput) else ComposeOutput.model_validate(result)
            return TurnOutput.from_compose(prose, location_id, events)
        except Exception:  # noqa: BLE001 - any model/parse failure falls through to retry/fallback
            continue
    fallback = ComposeOutput(narration=FALLBACK_NARRATION, choices=previous_choices or FALLBACK_CHOICES)
    return TurnOutput.from_compose(fallback, location_id, events)


def build_dm_graph(llm: Any, tools: list[BaseTool], checkpointer: Any = None):
    reasoner = llm.bind_tools(tools)

    def load_state(state: DMState) -> dict:
        update: dict = {}
        if not state.get("character"):
            update["character"] = DEFAULT_CHARACTER.model_dump()
        if not state.get("location_id"):
            update["location_id"] = START_LOCATION_ID
        messages = state.get("messages") or []
        if not messages or not isinstance(messages[-1], HumanMessage):
            update["messages"] = [HumanMessage(OPENING_CUE)]
        return update

    def dm_reason(state: DMState) -> dict:
        character = Character.model_validate(state["character"])
        location = LOCATIONS[state["location_id"]]
        system = SystemMessage(render_dm_system(character, location))
        return {"messages": [reasoner.invoke([system, *_sendable(state["messages"])])]}

    def route(state: DMState) -> str:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        if calls and _tool_calls_used(state["messages"]) + len(calls) <= MAX_TOOL_CALLS_PER_TURN:
            return "tools"
        return "compose"

    def compose(state: DMState) -> dict:
        previous = (state.get("turn") or {}).get("choices")
        turn = compose_turn(
            llm, state["messages"], state["location_id"], roll_events(state["messages"]), previous
        )
        text = turn.narration + "\n\n" + "\n".join(f"- {c}" for c in turn.choices)
        return {"turn": turn.model_dump(), "messages": [AIMessage(content=text)]}

    builder = StateGraph(DMState)
    builder.add_node("load_state", load_state)
    builder.add_node("dm_reason", dm_reason)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_node("compose", compose)
    builder.add_edge(START, "load_state")
    builder.add_edge("load_state", "dm_reason")
    builder.add_conditional_edges("dm_reason", route, {"tools": "tools", "compose": "compose"})
    builder.add_edge("tools", "dm_reason")
    builder.add_edge("compose", END)
    return builder.compile(checkpointer=checkpointer)
