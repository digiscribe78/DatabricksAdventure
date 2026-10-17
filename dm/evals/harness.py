"""Play one scenario turn in-process: a seeded game, stub memory, seeded dice and the real DM graph."""

import random
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import mlflow
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver

import agent.tools.dice as dice
from agent.dm_graph import build_dm_graph
from agent.tools import all_tools
from evals.scenarios import Scenario
from rpg.store import InMemoryStore, load_npc_cards

NPC_DIR = Path(__file__).resolve().parents[2] / "content" / "npcs"
PLAYER = "eval-player"
DETAILS = "eval.details"  # span attribute the code scorers read back from the trace
NUMERAL = re.compile(r"\b\d+\b")


def stub_memory_tools(memories: list[str]) -> list[BaseTool]:
    """The runtime's memory tools, same names and arguments, but nothing is ever written."""

    @tool
    def remember(fact: str, topic: str) -> str:
        """Persist a durable fact about the user in long-term memory."""
        return "stored"

    @tool
    def recall(query: str) -> str:
        """Search the user's long-term memory for facts relevant to the query."""
        return "\n".join(f"- {m}" for m in memories) or "No relevant memories."

    return [remember, recall]


def seed_store(s: Scenario) -> InMemoryStore:
    store = InMemoryStore(load_npc_cards(NPC_DIR))
    store.create_adventure(s.id, PLAYER, s.state.name, s.state.archetype)
    game = store.load(s.id)
    overrides = {k: v for k, v in {"hp": s.state.hp, "gold": s.state.gold, "inventory": s.state.inventory}.items()
                 if v is not None}
    store.commit(s.id, game.model_copy(update={
        "character": game.character.model_copy(update=overrides),
        "location_id": s.state.location_id, "flags": dict(s.state.flags)}))
    here = store.load(s.id)  # reloaded so the NPCs at the seeded location are present
    for npc in here.npcs:
        npc.disposition = s.state.dispositions.get(npc.npc_id, npc.disposition)
    store.commit(s.id, here)
    return store


def numbers_in(value: Any) -> set[int]:
    """Every whole number in a value: ints, integral floats, and numerals inside strings."""
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {value}
    if isinstance(value, float):
        return {int(value)} if value.is_integer() else set()
    if isinstance(value, str):
        return {int(n) for n in NUMERAL.findall(value)}
    if isinstance(value, dict):
        return set().union(*(numbers_in(v) for v in value.values()))
    if isinstance(value, (list, tuple, set)):
        return set().union(*(numbers_in(v) for v in value))
    return set()


@contextmanager
def seeded_dice(seed: int) -> Iterator[None]:
    previous = dice.RNG
    dice.RNG = random.Random(seed)
    try:
        yield
    finally:
        dice.RNG = previous


def play_turn(s: Scenario, llm: Any) -> dict:
    """Play the scenario's history, then its input; return the turn and what the code scorers need."""
    store = seed_store(s)
    before = store.load(s.id)
    graph = build_dm_graph(llm, [*all_tools(), *stub_memory_tools(s.memories)], checkpointer=InMemorySaver(),
                           store=store, recall=lambda _actor: list(s.memories))
    config = {"configurable": {"thread_id": s.id, "actor_id": PLAYER}}
    with seeded_dice(s.dice_seed):
        for line in s.history:
            graph.invoke({"messages": [{"role": "user", "content": line}]}, config)
        earlier = {m.id for m in graph.get_state(config).values.get("messages", [])}
        seen: dict[str, Any] = {}
        last: dict = {}
        for last in graph.stream({"messages": [{"role": "user", "content": s.input}]}, config, stream_mode="values"):
            seen.update({m.id: m for m in last.get("messages", []) if m.id not in earlier})
    after = store.load(s.id)
    results = [m.content for m in seen.values() if isinstance(m, ToolMessage)]
    known = numbers_in(results) | numbers_in(before.model_dump()) | numbers_in(after.model_dump())
    return {
        "turn": last["turn"],
        "tool_calls": [c["name"] for m in seen.values() if isinstance(m, AIMessage) for c in m.tool_calls],
        "flags": dict(after.flags),
        "location_id": after.location_id,
        "known_numbers": sorted(known),
        "guardrail": next((e["detail"].get("policy") for e in last["turn"]["events"] if e["type"] == "guardrail"), None),
        "category": s.category,
    }


def make_predict_fn(scenarios: list[Scenario], llm: Any) -> Callable[[str, str], dict]:
    by_id = {s.id: s for s in scenarios}

    # Traced here, not left to evaluate(): with LangChain autolog on, the graph would otherwise make the
    # root trace itself and evaluate() would stop wrapping this call, leaving no span for the details.
    @mlflow.trace(name="dm_turn")
    def predict(scenario_id: str, player_input: str) -> dict:  # noqa: ARG001 - the judges read player_input
        result = play_turn(by_id[scenario_id], llm)
        # evaluate() first calls this once untraced to validate it, so there may be no span.
        if (span := mlflow.get_current_active_span()) is not None:
            span.set_attribute(DETAILS, result)
        return {"narration": result["turn"]["narration"], "choices": result["turn"]["choices"]}

    return predict
