"""Record each turn's pre-turn game state on its MLflow trace.

A trace's input is only the player's words, but the DM's reply also depends on the saved game and
the earlier turns. With this metadata a production trace can be replayed as an eval scenario
(evals/from_traces.py). Values are strings (MLflow's rule) and hold nothing secret.
"""

import json
import logging

import mlflow
from langchain_core.messages import AnyMessage, HumanMessage

from agent.prompts import CONTINUE_CUE, OPENING_CUE
from rpg.campaign import act
from rpg.state import GameState

logger = logging.getLogger(__name__)
_CUES = (OPENING_CUE, CONTINUE_CUE)


def state_metadata(game: GameState, messages: list[AnyMessage]) -> dict[str, str]:
    players = [m for m in messages if isinstance(m, HumanMessage)]
    last = players[-1].content if players else OPENING_CUE
    kind = "new_game" if last == OPENING_CUE else "continue" if last == CONTINUE_CUE else "turn"
    c = game.character
    return {
        "adventure.location_id": game.location_id,
        "adventure.act": str(act(dict(game.flags))),
        "adventure.flags": json.dumps(dict(game.flags), sort_keys=True),
        "adventure.character": json.dumps({"name": c.name, "archetype": c.archetype, "hp": c.hp, "max_hp": c.max_hp,
                                           "gold": c.gold, "inventory": list(c.inventory)}),
        "adventure.npcs": json.dumps({n.npc_id: n.disposition for n in game.npcs}, sort_keys=True),
        "adventure.turn_number": str(sum(1 for m in players if m.content not in _CUES)),
        "adventure.turn_kind": kind,
    }


def tag_trace(metadata: dict[str, str], user: str | None = None) -> None:
    """Add metadata to the current trace, if there is one. Never breaks a turn."""
    try:
        if mlflow.get_current_active_span() is None:
            return
        mlflow.update_current_trace(metadata=metadata, **({"user": user} if user else {}))
    except Exception:  # noqa: BLE001 - tracing is a bonus, the turn is not
        logger.warning("tagging the trace failed", exc_info=True)
