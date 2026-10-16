#!/usr/bin/env bash
# Plays three DM turns in one session against a running agent and checks each returns a turn.
set -euo pipefail
BASE="${1:-http://localhost:8000}"
SESSION=$(uuidgen)

turn() {
  local content="$1" body
  if [ -z "$content" ]; then
    body=$(jq -n --arg id "$(uuidgen)" --arg s "$SESSION" '{id:$id, session_id:$s, input:{messages:[]}}')
  else
    body=$(jq -n --arg id "$(uuidgen)" --arg s "$SESSION" --arg c "$content" \
      '{id:$id, session_id:$s, input:{messages:[{role:"user", content:$c}]}}')
  fi
  local out
  out=$(curl -sS --fail "$BASE/api/invocations" -H 'Content-Type: application/json' -d "$body")
  echo "$out" | jq -e '.output.turn.narration | length > 0' >/dev/null || { echo "FAIL: no narration"; echo "$out"; exit 1; }
  echo "$out" | jq -e '.output.turn.choices | length >= 2' >/dev/null || { echo "FAIL: <2 choices"; echo "$out"; exit 1; }
  echo "--- turn: ${content:-<opening>}"
  echo "$out" | jq -r '.output.turn.narration, (.output.turn.choices[] | "  > " + .), (.output.turn.events[] | "  🎲 " + .summary)'
}

turn ""
turn "I try to charm Marta into telling me why the Archive is sealed."
turn "I head for the door to the Delta Crossing."
echo "SMOKE OK (session $SESSION)"
