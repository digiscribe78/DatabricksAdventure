# Databricks Adventure: Replayable Traces and Whole-Adventure Evals

- **Date:** 2026-11-07
- **Status:** Approved; to be implemented
- **Builds on:** M6 evals (`2026-10-17-m6-evals-design.md`) and live monitoring.
- **Prompted by:** review feedback that a trace's input is only the player's message. The DM's reply also depends on the saved game in Lakebase and the earlier turns, so a production trace can't be replayed on its own.

## 1. Intent

| Piece | What it does |
|---|---|
| Game state on every trace | Each turn's trace records the **pre-turn** game state as trace metadata, plus the player (`mlflow.trace.user`) |
| Trace → scenario | `make eval-capture` turns a chosen production trace into a replayable eval scenario: the state from the metadata, the input, and the session's earlier player turns as history |
| Whole-adventure judging | Session-level judges (`ConversationCompleteness`, `UserFrustration`, and offline also `KnowledgeRetention`) score whole games: live through monitoring, offline through `make eval-sessions` |

## 2. What's there today (2026-11-07)

- Every trace already carries `mlflow.trace.session` (set by Agent Runtime), so a game's turns already group into a session.
- The trace input and preview are only the player's message. There's no game state and no `mlflow.trace.user`.
- `make eval` scenarios seed their own state, so offline evals don't depend on traces.
- MLflow 3.17.1 has the session-level judges and `evaluate(data=<traces>)` for them (session scorers require traces and no `predict_fn`).

## 3. Game state on the trace

At the start of each turn (`load_state`, once the save is loaded), the DM calls `mlflow.update_current_trace(metadata=…, user=<actor>)`. It's a no-op when there's no active trace, as in tests and local runs without tracing.

| Metadata key | Value (strings only, as MLflow requires) |
|---|---|
| `adventure.location_id` | e.g. `delta-crossing` |
| `adventure.act` | `1`, `2` or `3` |
| `adventure.flags` | JSON of the quest flags |
| `adventure.character` | JSON: archetype, name, hp, max_hp, gold, inventory |
| `adventure.npcs` | JSON `{npc_id: disposition}` for the NPCs present |
| `adventure.turn_number` | Count of player turns so far in the session, this one included |
| `adventure.turn_kind` | `new_game`, `continue` or `turn` |
| `adventure.outcome` | Set in `compose`: `normal`, `refused` (guardrail), `fallback` or `game_over` |

The actor is already a hashed principal id, not an email, so it's safe as `mlflow.trace.user`. The values are capped (inventory and flags are small), and nothing secret is recorded.

## 4. Trace → scenario: `make eval-capture`

`evals/from_traces.py`:
- `scenario_from_trace(trace, earlier_inputs, scenario_id, category) -> Scenario`: builds a `SeedState` from the metadata (location, flags, archetype, name, hp, gold, inventory, the dispositions of the NPCs present), with `input` = the player's message and `history` = the session's earlier player messages, in order.
- `make eval-capture PROFILE=… TRACE=<trace id> ID=<scenario id> CATEGORY=<category>` fetches the trace, plus the earlier traces in the same session for the history. It writes `dm/evals/captured/<id>.yaml` with an empty `expect` block for a human to fill in, and refuses traces without `adventure.*` metadata (made before this change).
- **Loading:** `load_scenarios()` keeps reading `scenarios.yaml`. `make eval` also loads `evals/captured/*.yaml`, and the same strict validation and `problems()` checks apply.
- Turns from the opening scene and continue cues have no player input, so they're refused with a clear message.

## 5. Whole-adventure judging

- **Live:** `make monitoring` also registers `conversation_completeness` and `user_frustration` (session-level, sample rate 1.0) on `dm-traces`. The platform job already runs a session pass ("session-level scoring") on each run.
- **Offline:** `make eval-sessions PROFILE=…` (`evals/sessions.py`):
  1. searches `dm-traces` for the last `DAYS` (default 7);
  2. keeps sessions with at least `MIN_TURNS` player turns (default 4);
  3. runs `mlflow.genai.evaluate(data=traces, scorers=[ConversationCompleteness(), UserFrustration(), KnowledgeRetention()])`;
  4. logs the result to `dm-evals` and prints one line per session.

  It's report only, like `make eval`.

## 6. Testing

- **Offline:**
  - the metadata builder: keys, string values, the act, turn kinds, and a no-op without an active trace;
  - `compose` sets the outcome;
  - `scenario_from_trace`: state, input and history mapped, refusing metadata-less and cue traces, and the result passing `problems()`;
  - captured files loaded by `make eval`'s loader;
  - `choose_sessions`: grouping, the turn threshold, newest first;
  - the monitoring judges list includes the two session judges.
- **Live (second install, profile `databricks-adventure`):**
  1. `deploy-agent`;
  2. play the smoke test;
  3. the latest trace carries the `adventure.*` metadata and the user;
  4. `make eval-capture` one turn, and replay it with the harness;
  5. `make monitoring` shows the session judges;
  6. `make eval-sessions` scores the smoke session.

## 7. Out of scope

- A simulated player (`ConversationSimulator`) for scripted whole adventures offline: a possible follow-up.
- Backfilling metadata onto old traces.
