#!/usr/bin/env bash
# Plays three DM turns in one session against a running agent and checks each returns a turn.
set -euo pipefail
BASE="${1:-http://localhost:8000}"
SESSION=$(uuidgen)

turn() {
  local content="$1" extra="${2:-}" body out
  [ -n "$extra" ] || extra='{}'
  body=$(jq -n --arg id "$(uuidgen)" --arg s "$SESSION" --arg c "$content" --argjson extra "$extra" \
    '{id:$id, session_id:$s, input:({messages:(if $c == "" then [] else [{role:"user", content:$c}] end), actor:"smoke-player"} + $extra)}')
  out=$(curl -sS --fail "$BASE/api/invocations" -H 'Content-Type: application/json' -d "$body")
  echo "$out" | jq -e '.output.turn.narration | length > 0' >/dev/null || { echo "FAIL: no narration"; echo "$out"; exit 1; }
  echo "$out" | jq -e '.output.turn.choices | length >= 2' >/dev/null || { echo "FAIL: <2 choices"; echo "$out"; exit 1; }
  echo "--- turn: ${content:-<new game>}"
  echo "$out" | jq -r '.output.turn.narration, (.output.turn.choices[] | "  > " + .),
    "  📍 " + .output.turn.location_id,
    (.output.turn.events[] | ({"roll":"🎲","lore":"📚","attack":"⚔️ ","state":"💾"}[.type] // "•") + " " + .summary)'
}

turn "" '{"new_game":{"name":"Brannoc","archetype":"warrior"}}'
turn "I try to charm Marta into telling me why the Archive is sealed."
turn "I buy a lantern from Marta for two gold."
turn "I head out of the inn and down to the Delta Crossing."
turn "I pay the Sweeper his two gold for the crossing."
echo "SMOKE OK (session $SESSION)"
