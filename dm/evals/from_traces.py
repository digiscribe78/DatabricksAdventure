"""make eval-capture: turn a production trace into a replayable eval scenario.

Traces record the pre-turn game state as adventure.* metadata (agent/trace_state.py). Here that
state seeds a scenario, the player's message is the input, and the session's earlier player
messages are the history. Fill in the scenario's expect block by hand.
"""

import json
import sys
from pathlib import Path

import yaml

from evals.scenarios import CAPTURED, Scenario
from rpg.store import load_npc_cards

NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"
TRACES_EXPERIMENT = "/Shared/databricks-adventure/dm-traces"


def scenario_from_trace(metadata: dict, player_input: str, earlier_inputs: list[str], scenario_id: str,
                        category: str) -> Scenario:
    if "adventure.location_id" not in metadata:
        raise ValueError("this trace has no adventure state (made before traces recorded it)")
    if metadata.get("adventure.turn_kind") != "turn" or not (player_input or "").strip():
        raise ValueError("this trace has no player input (an opening scene or a continue)")
    where = metadata["adventure.location_id"]
    homes = {c.npc_id: c.home_location_id for c in load_npc_cards(NPCS)}
    c = json.loads(metadata.get("adventure.character", "{}"))
    npcs = json.loads(metadata.get("adventure.npcs", "{}"))
    return Scenario.model_validate({
        "id": scenario_id, "category": category, "input": player_input, "history": list(earlier_inputs),
        "state": {"location_id": where, "archetype": c.get("archetype", "warrior"), "name": c.get("name", "Tess"),
                  "hp": c.get("hp"), "gold": c.get("gold"), "inventory": c.get("inventory"),
                  "flags": json.loads(metadata.get("adventure.flags", "{}")),
                  "dispositions": {n: d for n, d in npcs.items() if homes.get(n) == where}},
    })


def write_scenario(s: Scenario, folder: Path = CAPTURED) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{s.id}.yaml"
    doc = s.model_dump(exclude_defaults=True)
    doc["expect"] = {"guidelines": []}  # fill in what a good DM turn does here
    out.write_text("# Captured from a production trace; fill in expect before relying on it.\n"
                   + yaml.safe_dump([doc], sort_keys=False, allow_unicode=True))
    return out


def _player_input(trace) -> str:
    inputs = trace.info.trace_metadata.get("mlflow.traceInputs") or trace.info.request_preview or ""
    try:
        doc = json.loads(inputs)
    except (TypeError, ValueError):
        return inputs
    messages = doc.get("messages") if isinstance(doc, dict) else None
    users = [m.get("content", "") for m in messages or [] if isinstance(m, dict) and m.get("role") == "user"]
    return users[-1] if users else ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("usage: python -m evals.from_traces <trace_id> <scenario_id> <category>", file=sys.stderr)
        return 2
    trace_id, scenario_id, category = args
    import mlflow

    mlflow.set_tracking_uri("databricks")
    trace = mlflow.get_trace(trace_id)
    md = trace.info.trace_metadata
    session = md.get("mlflow.trace.session")
    earlier = []
    if session:
        exp = mlflow.get_experiment_by_name(TRACES_EXPERIMENT)
        found = mlflow.search_traces(locations=[exp.experiment_id], return_type="list", max_results=200,
                                     filter_string=f"metadata.`mlflow.trace.session` = '{session}'",
                                     order_by=["timestamp_ms ASC"])
        earlier = [_player_input(t) for t in found
                   if t.info.timestamp_ms < trace.info.timestamp_ms
                   and t.info.trace_metadata.get("adventure.turn_kind") == "turn"]
        earlier = [e for e in earlier if e]
    try:
        s = scenario_from_trace(md, _player_input(trace), earlier, scenario_id, category)
    except ValueError as e:
        print(f"can't capture {trace_id}: {e}", file=sys.stderr)
        return 1
    print(f"wrote {write_scenario(s)} ({len(earlier)} earlier turns as history)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
