from pathlib import Path

from lore.manifest import doc_metadata, load_manifest

MANIFEST = Path(__file__).resolve().parents[2] / "content" / "manifest.yaml"


def test_doc_metadata_keys_are_pdf_stems():
    meta = doc_metadata(load_manifest(MANIFEST))
    assert meta["delta-crossing"] == {"doc_type": "location", "location_id": "delta-crossing"}
    assert meta["rules"] == {"doc_type": "rules", "location_id": "global"}


def test_doc_metadata_from_inline_manifest():
    m = {"documents": [{"file": "a-b.md", "doc_type": "primer", "location_id": "global"}]}
    assert doc_metadata(m) == {"a-b": {"doc_type": "primer", "location_id": "global"}}
