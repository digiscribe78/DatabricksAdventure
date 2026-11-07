# Replayable Traces and Whole-Adventure Evals: Implementation Plan

**Spec:** `docs/superpowers/specs/2026-11-07-trace-state-design.md`

**Global constraints:**
- Trace metadata values are strings, with no secrets or emails (the actor is a hashed id).
- Tracing calls never break a turn: they're a no-op without an active trace, and failures are swallowed.
- Captured scenarios pass the same strict validation as `scenarios.yaml`.
- Report only: `make eval-sessions` exits 0 whatever the scores.
- Commits end with `Co-authored-by: Isaac <no-reply@databricks.com>`.
- British English.
- Live steps use profile `databricks-adventure`, catalog `databricks_adventure_catalog`.

## Task 1: Game state on every trace

**Files:** `dm/agent/trace_state.py` (new); `dm/agent/dm_graph.py` (`load_state` and `compose`); test `dm/tests/test_trace_state.py`.

- **`state_metadata(game, messages) -> dict[str, str]`** returns the `adventure.*` keys from spec §3:
  - **`turn_kind`:** from the last player message. `OPENING_CUE` is `new_game`, `CONTINUE_CUE` is `continue`, anything else is `turn`.
  - **`turn_number`:** the number of player messages that aren't cues.
- **`tag_trace(metadata, user=None)`** calls `mlflow.update_current_trace(metadata=…, user=…)` only when `mlflow.get_current_active_span()` exists, and swallows any error.
- **`load_state`:** calls `tag_trace(state_metadata(game, messages), user=actor)` after loading.
- **`compose`:** calls `tag_trace({"adventure.outcome": …})` with `refused`, `fallback`, `game_over` or `normal`.
- **Tests:**
  - the keys and string values;
  - the three turn kinds;
  - the turn number skipping cues;
  - a no-op without a trace;
  - inside `mlflow.trace` with the `local_mlflow` fixture, the trace carries the metadata and user after a graph turn, with the outcome `normal`, and `refused` for a blocked turn.

## Task 2: Trace → scenario

**Files:** `dm/evals/from_traces.py` (new); `dm/evals/scenarios.py` (`CAPTURED`, `load_all_scenarios()`); `dm/evals/run.py` (uses `load_all_scenarios`); `Makefile` (`eval-capture`); test `dm/tests/test_from_traces.py`.

- **`scenario_from_trace(metadata, player_input, earlier_inputs, scenario_id, category) -> Scenario`** builds the `SeedState` from the metadata (NPC dispositions kept only for NPCs whose home is the location). It raises `ValueError` without `adventure.location_id`, or when the player input is empty or a cue.
- **`load_all_scenarios()`** loads `scenarios.yaml` plus `evals/captured/*.yaml`, and rejects duplicate ids across files.
- **CLI** (`python -m evals.from_traces <trace_id> <scenario_id> <category>`):
  1. fetch the trace;
  2. find the earlier traces in the same session (`mlflow.trace.session`), oldest first, and take their player inputs;
  3. write `evals/captured/<id>.yaml` with an empty `expect`.

  It needs `MLFLOW_TRACING_SQL_WAREHOUSE_ID`, which the make target sets from the default warehouse.
- **Tests:**
  - the mapping (state, flags, character, dispositions, history);
  - the errors;
  - the result passes `problems()`;
  - the YAML round-trips through `load_all_scenarios` in a temp dir;
  - duplicate ids across files are refused.

## Task 3: Session judges, live and offline

**Files:** `dm/devtools/monitoring.py` (`JUDGES` gains `conversation_completeness`, `user_frustration` at 1.0); `dm/evals/sessions.py` (new); `Makefile` (`eval-sessions`); tests `dm/tests/test_monitoring.py`, `dm/tests/test_eval_sessions.py`.

- **`choose_sessions(traces, min_turns) -> dict[str, list]`** groups by `mlflow.trace.session`, counts `adventure.turn_kind == "turn"` traces, keeps sessions with at least `min_turns`, and puts the newest first.
- **`main()`:**
  1. search `dm-traces` from the last `DAYS` days;
  2. pick the sessions;
  3. run `mlflow.genai.evaluate(data=<their traces>, scorers=[ConversationCompleteness(), UserFrustration(), KnowledgeRetention()])` into `dm-evals`;
  4. print one line per session.

  Report only.
- **Tests:**
  - grouping;
  - the threshold;
  - ordering;
  - traces without a session are ignored;
  - the monitoring judges list.

## Task 4: Live, then docs

1. `make deploy-agent PROFILE=databricks-adventure CATALOG=databricks_adventure_catalog`
2. Run the smoke test. The latest trace has the `adventure.*` metadata and the user.
3. `make eval-capture` the smoke's "lore probe" turn, then replay it with the harness.
4. `make monitoring PROFILE=databricks-adventure` lists five judges.
5. `make eval-sessions PROFILE=databricks-adventure` scores the smoke session.
6. **Docs:** the README (Evaluate the DM: capture and sessions), the Guide's Evaluation page, and spec Status → implemented.
