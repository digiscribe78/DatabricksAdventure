"""Lore tool: the DM looks up the world's lorebooks (AI Search) before describing it."""

import json
import os
from typing import Annotated, Callable

from databricks_agentkit import workspace_client
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from rpg.world import LOCATIONS

NUM_RESULTS = 4
COLUMNS = ["chunk_text", "source", "page", "doc_type", "location_id"]


def scope(location_id: str) -> list[str]:
    """Lore visible from a location: its own, its neighbours' (rumours travel) and the global books."""
    exits = list(LOCATIONS[location_id].exits) if location_id in LOCATIONS else []
    return [location_id, *exits, "global"]


def _query_index(query: str, locations: list[str]) -> list[dict]:
    index = os.getenv("LORE_INDEX")
    if not index:
        raise RuntimeError("LORE_INDEX is not set")
    response = workspace_client().vector_search_indexes.query_index(
        index_name=index,
        columns=COLUMNS,
        query_text=query,
        num_results=NUM_RESULTS,
        filters_json=json.dumps({"location_id": locations}),
    )
    names = [c.name for c in response.manifest.columns]
    passages = []
    for row in response.result.data_array or []:
        r = dict(zip(names, row))
        passages.append({
            "text": r["chunk_text"], "source": r["source"], "page": int(r["page"]),
            "doc_type": r["doc_type"], "location_id": r["location_id"],
        })
    return passages


SEARCH: Callable[[str, list[str]], list[dict]] = _query_index


@tool
def search_lore(query: str, state: Annotated[dict, InjectedState]) -> dict:
    """Search the Kingdom of Sparkia's lorebooks for places, people, creatures, history and rules.

    Call this before describing anything the player hasn't seen yet, before introducing a named
    character or creature, and whenever you need a rule. Write a short natural-language query
    such as "the ferryman at the Delta Crossing". Stay consistent with what it returns.
    """
    try:
        passages = SEARCH(query, scope(state.get("location_id", "")))
    except Exception as e:  # noqa: BLE001 - lore outages must not break the turn
        return {"error": f"lore unavailable: {e}"}
    return {"query": query, "passages": passages}
