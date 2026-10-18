"""Lore tool: the DM looks up the world's lorebooks (AI Search) before describing it."""

import json
import logging
import os
from typing import Annotated, Callable

import mlflow
from databricks_agentkit import workspace_client
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from mlflow.entities import SpanType

from rpg.world import LOCATIONS

logger = logging.getLogger(__name__)

NUM_RESULTS = 4
COLUMNS = ["chunk_text", "source", "page", "doc_type", "location_id"]


def scope(location_id: str, flags: dict) -> list[str]:
    """Lore visible from a location: its own, its open neighbours' (rumours travel) and the global books.

    Gated neighbours stay hidden until their gate opens, so no lorebook spoils a place the story hasn't
    reached (the Swamp's book names Silo's Keep).
    """
    loc = LOCATIONS.get(location_id)
    exits = [e for e in loc.exits if loc.barrier(e, flags) is None] if loc else []
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


def documents(passages: list[dict]) -> list[dict]:
    """Passages as retriever documents, the shape MLflow's retrieval judges read."""
    return [{"page_content": p["text"],
             "metadata": {"doc_uri": p["source"], "page": p["page"], "location_id": p["location_id"]}}
            for p in passages]


def _retrieve(query: str, locations: list[str]) -> list[dict]:
    with mlflow.start_span(name="lore_index", span_type=SpanType.RETRIEVER) as span:
        span.set_inputs({"query": query, "locations": locations})
        passages = SEARCH(query, locations)
        span.set_outputs(documents(passages))
    return passages


@tool
def search_lore(query: str, state: Annotated[dict, InjectedState]) -> dict:
    """Search the Kingdom of Sparkia's lorebooks for places, people, creatures, history and rules.

    Call this before describing anything the player hasn't seen yet, before introducing a named
    character or creature, and whenever you need a rule. Write a short natural-language query
    such as "the ferryman at the Delta Crossing". Stay consistent with what it returns.
    """
    try:
        passages = _retrieve(query, scope(state.get("location_id", ""), state.get("flags") or {}))
    except Exception as e:  # noqa: BLE001 - lore outages must not break the turn
        logger.warning("lore lookup failed for %r", query, exc_info=True)  # never silent: the Glass shows it too
        return {"query": query, "error": f"lore unavailable: {e}"}
    return {"query": query, "passages": passages}
