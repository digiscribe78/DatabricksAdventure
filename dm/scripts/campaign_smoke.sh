#!/usr/bin/env bash
# Plays Act 1 against the deployed DM and probes a story gate. Prints location and flags per turn.
set -euo pipefail
BASE="${1:?usage: campaign_smoke.sh <dm-url>}"
TOKEN="${TOKEN:?set TOKEN=$(databricks auth token -p <profile> | jq -r .access_token)}"
SESSION=$(uuidgen)
turn() {
  local input="$1"
  jq -n --arg id "$(uuidgen)" --arg s "$SESSION" --argjson input "$input" '{id:$id, session_id:$s, input:$input}' |
    curl -sS --fail "$BASE/api/invocations" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d @- |
    jq -r '"📍 " + .output.game.location_id + "  flags=" + (.output.game.flags | keys | join(",")) + "  open=" + ([.output.game.exits[] | select(.open) | .id] | join(",")),
           (.output.turn.events[] | "  " + .type + ": " + .summary)'
}
msg() { jq -n --arg c "$1" '{messages:[{role:"user", content:$c}]}'; }
echo "--- new game"; turn '{"messages":[],"new_game":{"name":"Tess","archetype":"warrior"}}'
echo "--- vow";      turn "$(msg 'I promise Marta I will find Keeper Aldric.')"
echo "--- to delta"; turn "$(msg 'I head out to the Delta Crossing.')"
echo "--- archive";  turn "$(msg 'I take the road upriver to the Unity Archive.')"
echo "--- gate probe: straight to the Forge"; turn "$(msg 'Without waiting, I march straight off to the Spark Forge.')"
echo "--- doors";    turn "$(msg 'I knock on the bronze doors and call out for Keeper Aldric.')"
echo "CAMPAIGN SMOKE DONE (session $SESSION)"
