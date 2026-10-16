import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest_job import chunks_for_rows, index_spec  # noqa: E402

META = {"delta-crossing": {"doc_type": "location", "location_id": "delta-crossing"}}


def parsed(text="Body.", errors=()):
    return json.dumps({
        "document": {"elements": [
            {"id": 0, "type": "title", "content": "T", "bbox": [{"page_id": 0}]},
            {"id": 1, "type": "text", "content": text, "bbox": [{"page_id": 0}]},
        ]},
        "error_status": list(errors),
    })


def test_rows_become_chunks_tagged_from_manifest():
    chunks, skipped = chunks_for_rows([("dbfs:/Volumes/c/s/lore/pdfs/delta-crossing.pdf", parsed())], META)
    assert skipped == []
    assert chunks[0].source == "delta-crossing"
    assert chunks[0].location_id == "delta-crossing"


def test_parse_errors_and_unknown_documents_are_skipped_not_fatal():
    rows = [
        ("/Volumes/c/s/lore/pdfs/delta-crossing.pdf", parsed(errors=[{"error_message": "bad", "page_id": 0}])),
        ("/Volumes/c/s/lore/pdfs/stray.pdf", parsed()),
    ]
    chunks, skipped = chunks_for_rows(rows, META)
    assert chunks == []
    assert sorted(skipped) == ["delta-crossing", "stray"]


def test_index_spec_uses_triggered_managed_embeddings():
    spec = index_spec("c.s.lore_chunks", "databricks-gte-large-en")
    assert spec["source_table"] == "c.s.lore_chunks"
    assert spec["pipeline_type"] == "TRIGGERED"
    assert spec["embedding_source_columns"] == [
        {"name": "chunk_text", "embedding_model_endpoint_name": "databricks-gte-large-en"}
    ]
    assert set(spec["columns_to_sync"]) == {"chunk_id", "chunk_text", "doc_type", "location_id", "source", "page"}


def test_index_synced_requires_ready_and_matching_row_count():
    from types import SimpleNamespace

    from ingest_job import index_synced

    def status(ready, rows):
        return SimpleNamespace(status=SimpleNamespace(ready=ready, indexed_row_count=rows))

    assert index_synced(status(True, 27), 27) is True
    assert index_synced(status(True, 27), 30) is False  # ready from an earlier build, sync not caught up
    assert index_synced(status(False, 30), 30) is False
    assert index_synced(SimpleNamespace(status=None), 30) is False
