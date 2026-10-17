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


def test_scope_is_location_exits_and_global():
    assert lore.scope("medallion-inn") == ["medallion-inn", "delta-crossing", "unity-archive", "global"]


def test_search_uses_state_location_not_model_input(calls):
    out = lore.search_lore.invoke({"query": "ferryman", "state": STATE})
    assert out == {"query": "ferryman", "passages": [PASSAGE]}
    assert calls == [("ferryman", ["medallion-inn", "delta-crossing", "unity-archive", "global"])]


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
