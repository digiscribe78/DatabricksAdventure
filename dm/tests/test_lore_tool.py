import agent.tools.lore as lore
import pytest
from agent.tools import all_tools

STATE = {"location_id": "medallion-inn"}
PASSAGE = {"text": "The Sweeper...", "source": "bestiary", "page": 1, "doc_type": "bestiary", "location_id": "global"}


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake(query, scope):
        seen.append((query, scope))
        return [PASSAGE]

    monkeypatch.setattr(lore, "SEARCH", fake)
    return seen


def test_tool_is_auto_registered():
    assert "search_lore" in {t.name for t in all_tools()}


def test_scope_is_location_open_exits_and_global():
    assert lore.scope("medallion-inn", {}) == ["medallion-inn", "delta-crossing", "global"]
    assert lore.scope("medallion-inn", {"knows_cellar_route": "yes"}) == [
        "medallion-inn", "delta-crossing", "unity-archive", "global"]


def test_scope_hides_the_swamp_and_keep_until_the_catalog():
    # The Swamp's lorebook names Silo's Keep: it must not leak to the Delta before has_catalog.
    assert "data-swamp" not in lore.scope("delta-crossing", {})
    assert "data-swamp" in lore.scope("delta-crossing", {"has_catalog": "yes"})


def test_search_uses_state_location_not_model_input(calls):
    out = lore.search_lore.invoke({"query": "ferryman", "state": STATE})
    assert out == {"query": "ferryman", "passages": [PASSAGE]}
    assert calls == [("ferryman", ["medallion-inn", "delta-crossing", "global"])]


def test_search_scope_follows_the_story_flags_in_state(calls):
    lore.search_lore.invoke({"query": "cellar", "state": {**STATE, "flags": {"knows_cellar_route": "yes"}}})
    assert calls[-1][1] == ["medallion-inn", "delta-crossing", "unity-archive", "global"]


def test_model_only_supplies_query():
    schema = lore.search_lore.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"query"}


def test_backend_failure_returns_error_not_exception(monkeypatch):
    def boom(query, scope):
        raise RuntimeError("index not ready")

    monkeypatch.setattr(lore, "SEARCH", boom)
    out = lore.search_lore.invoke({"query": "x", "state": STATE})
    assert out["error"].startswith("lore unavailable")


def test_query_index_requires_lore_index(monkeypatch):
    monkeypatch.delenv("LORE_INDEX", raising=False)
    with pytest.raises(RuntimeError, match="LORE_INDEX"):
        lore._query_index("x", ["global"])


def test_query_index_parses_response(monkeypatch):
    from types import SimpleNamespace

    class FakeIndexes:
        def query_index(self, **kwargs):
            self.kwargs = kwargs
            cols = [SimpleNamespace(name=n) for n in [*lore.COLUMNS, "score"]]
            row = ["The Sweeper...", "bestiary", 1, "bestiary", "global", 0.9]
            return SimpleNamespace(manifest=SimpleNamespace(columns=cols), result=SimpleNamespace(data_array=[row]))

    fake = FakeIndexes()
    monkeypatch.setenv("LORE_INDEX", "c.s.lore_index")
    monkeypatch.setattr(lore, "workspace_client", lambda: SimpleNamespace(vector_search_indexes=fake))
    assert lore._query_index("ferryman", ["medallion-inn", "global"]) == [PASSAGE]
    assert fake.kwargs["index_name"] == "c.s.lore_index"
    assert fake.kwargs["num_results"] == lore.NUM_RESULTS
    assert fake.kwargs["filters_json"] == '{"location_id": ["medallion-inn", "global"]}'


def test_query_index_handles_empty_result(monkeypatch):
    from types import SimpleNamespace

    class FakeIndexes:
        def query_index(self, **kwargs):
            return SimpleNamespace(manifest=SimpleNamespace(columns=[]), result=SimpleNamespace(data_array=None))

    monkeypatch.setenv("LORE_INDEX", "c.s.lore_index")
    monkeypatch.setattr(lore, "workspace_client", lambda: SimpleNamespace(vector_search_indexes=FakeIndexes()))
    assert lore._query_index("x", ["global"]) == []


def test_documents_shape_for_the_groundedness_judge():
    assert lore.documents([PASSAGE]) == [{
        "page_content": "The Sweeper...",
        "metadata": {"doc_uri": "bestiary", "page": 1, "location_id": "global"},
    }]


def test_search_is_traced_as_a_retriever_span(calls, local_mlflow):
    import mlflow
    from mlflow.entities import SpanType

    @mlflow.trace
    def turn():
        return lore.search_lore.invoke({"query": "ferryman", "state": STATE})

    assert turn()["passages"] == [PASSAGE]
    trace = mlflow.get_trace(mlflow.get_last_active_trace_id())
    [span] = [s for s in trace.data.spans if s.span_type == SpanType.RETRIEVER]
    assert span.outputs == lore.documents([PASSAGE])


def test_a_lore_outage_is_logged(monkeypatch, caplog):
    def broken(query, scope):
        raise PermissionError("You do not have the SELECT privilege on 'cat.sch.lore_index'")

    monkeypatch.setattr(lore, "SEARCH", broken)
    with caplog.at_level("WARNING"):
        out = lore.search_lore.invoke({"query": "the three seals", "state": STATE})
    assert out["error"].startswith("lore unavailable") and out["query"] == "the three seals"
    assert any("lore lookup failed" in r.message for r in caplog.records)


def test_a_lore_outage_shows_in_the_glass_instead_of_vanishing():
    import json

    from agent.dm_graph import turn_events
    from langchain_core.messages import HumanMessage, ToolMessage

    failed = ToolMessage(content=json.dumps({"query": "the three seals", "error": "lore unavailable: no SELECT privilege"}),
                         name="search_lore", tool_call_id="c1")
    [event] = turn_events([HumanMessage("What are the three seals?"), failed])
    assert event.type == "warning" and event.summary.startswith("Lore unavailable")
    assert "no SELECT privilege" in event.summary
