"""make eval-sessions: score whole adventures (sessions) from the play traces.

The turn-by-turn evals judge one reply at a time; these session-level judges read a whole game:
did the conversation reach its goals, did the player get frustrated, did the DM remember what was
said earlier. Report only, like make eval.
"""

import os
import sys
import time
from collections import defaultdict

from mlflow.genai.scorers import ConversationCompleteness, KnowledgeRetention, UserFrustration

from evals.run import EXPERIMENT

TRACES_EXPERIMENT = "/Shared/databricks-adventure/dm-traces"
JUDGES = [ConversationCompleteness(), UserFrustration(), KnowledgeRetention()]


def choose_sessions(traces, min_turns: int) -> dict[str, list]:
    """Sessions with at least min_turns player turns, newest first; each keeps all its traces."""
    groups: dict[str, list] = defaultdict(list)
    for t in traces:
        if session := t.info.trace_metadata.get("mlflow.trace.session"):
            groups[session].append(t)
    keep = {s: ts for s, ts in groups.items()
            if sum(t.info.trace_metadata.get("adventure.turn_kind") == "turn" for t in ts) >= min_turns}
    return dict(sorted(keep.items(), key=lambda kv: -max(t.info.timestamp_ms for t in kv[1])))


def session_scores(trace) -> dict[str, tuple]:
    """The session judges' verdicts, which MLflow attaches to the session's first trace."""
    names = {j.name for j in JUDGES}
    found = {}
    for a in trace.info.assessments or []:
        if a.name in names:
            value = getattr(a, "value", None)
            if value is None and getattr(a, "feedback", None) is not None:
                value = a.feedback.value
            found[a.name] = (value, getattr(a, "rationale", "") or "")
    return found


def main() -> int:
    import mlflow

    days, min_turns = int(os.getenv("DAYS", "7")), int(os.getenv("MIN_TURNS", "4"))
    mlflow.set_tracking_uri("databricks")
    exp = mlflow.get_experiment_by_name(TRACES_EXPERIMENT)
    since = int((time.time() - days * 86400) * 1000)
    traces = mlflow.search_traces(locations=[exp.experiment_id], return_type="list", max_results=1000,
                                  filter_string=f"timestamp_ms > {since}")
    sessions = choose_sessions(traces, min_turns)
    if not sessions:
        print(f"No sessions with {min_turns}+ player turns in the last {days} days.")
        return 0
    mlflow.set_experiment(EXPERIMENT)
    result = mlflow.genai.evaluate(data=[t for ts in sessions.values() for t in ts], scorers=JUDGES)
    print(f"Whole adventures: {len(sessions)} sessions from the last {days} days")
    for session, ts in sessions.items():
        first = mlflow.get_trace(min(ts, key=lambda t: t.info.timestamp_ms).info.trace_id)
        turns = sum(t.info.trace_metadata.get("adventure.turn_kind") == "turn" for t in ts)
        scores = session_scores(first)
        line = " · ".join(f"{name} {scores[name][0]}" for name in (j.name for j in JUDGES) if name in scores)
        print(f"  {session[:12]}…  {turns} turns  {line or 'not scored'}")
    print(f"\nFull results: MLflow experiment {EXPERIMENT}, run {result.run_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
