"""Whole adventures: group the play traces by session and keep the ones worth judging."""

from types import SimpleNamespace

from evals.sessions import JUDGES, choose_sessions


def trace(session, kind="turn", ts=0):
    md = {"adventure.turn_kind": kind, **({"mlflow.trace.session": session} if session else {})}
    return SimpleNamespace(info=SimpleNamespace(trace_metadata=md, timestamp_ms=ts))


def test_sessions_with_enough_player_turns_are_kept_newest_first():
    traces = [trace("old", "new_game", 1), *[trace("old", ts=2 + i) for i in range(4)],
              trace("short", ts=50), trace("short", ts=51),
              trace("new", "continue", 90), *[trace("new", ts=91 + i) for i in range(5)],
              trace(None, ts=99)]
    chosen = choose_sessions(traces, min_turns=4)
    assert list(chosen) == ["new", "old"]
    assert len(chosen["old"]) == 5  # every trace in the session is kept, cues included


def test_the_whole_adventure_judges():
    assert [j.name for j in JUDGES] == ["conversation_completeness", "user_frustration", "knowledge_retention"]
    assert all(j.is_session_level_scorer for j in JUDGES)
