"""💡 Hints from game state: the next unfinished required beat, worded in content/hints.yaml.

No model call: code reads the campaign state, so a hint is never wrong and never costs a turn.
"""

from pathlib import Path

import yaml

from rpg.campaign import BEATS, FLAG_HOMES, act, game_over
from rpg.world import LOCATIONS

HINTS = Path(__file__).resolve().parents[2] / "content" / "hints.yaml"
HINTS_FALLBACK = Path(__file__).resolve().parents[1] / "hints.yaml"  # the deploy build's copy
OPTIONAL = {"knows_cellar_route", "forge_regret_shared", "echo_saw_past_life", "aldric_forgives_silo"}
REQUIRED = {n: [flag for flag, _, _ in beats if flag not in OPTIONAL] for n, beats in BEATS.items()}
HINT_KEY = {"crew_rescued": "seal_mines", "silo_wounds": "ending"}  # beats that share one hint
_cache: dict | None = None


def load_hints(path: Path = HINTS) -> dict[str, dict]:
    return yaml.safe_load((path if path.is_file() else HINTS_FALLBACK).read_text())


def next_hint(flags: dict, location_id: str, hints: dict | None = None) -> dict | None:
    global _cache
    if game_over(flags):
        return None
    if hints is None:
        _cache = _cache or load_hints()
        hints = _cache
    open_beats = [b for b in REQUIRED[act(flags)] if b not in flags]
    if not open_beats:
        return None
    beat = next((b for b in open_beats if FLAG_HOMES.get(b) == location_id), open_beats[0])
    h = hints[HINT_KEY.get(beat, beat)]
    where = LOCATIONS[FLAG_HOMES[beat]].name if FLAG_HOMES.get(beat) in LOCATIONS else ""
    return {"beat": beat, "where": where, "nudge": h["nudge"], "clearer": h["clearer"]}
