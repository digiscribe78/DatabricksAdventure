from lore.chunking import MAX_CHUNK_CHARS, chunk_document


def el(i, type_, content, page=0):
    return {"id": i, "type": type_, "content": content, "bbox": [{"coord": [0, 0, 1, 1], "page_id": page}]}


def doc(*elements):
    return {"document": {"pages": [], "elements": list(elements)}, "error_status": []}


def chunks_of(parsed):
    return chunk_document(parsed, source="delta-crossing", doc_type="location", location_id="delta-crossing")


def test_sections_become_chunks_with_heading_path():
    parsed = doc(
        el(0, "title", "The Delta Crossing"),
        el(1, "section_header", "The River"),
        el(2, "text", "Wide and cold."),
        el(3, "text", "It runs in layers."),
        el(4, "section_header", "Dangers", page=1),
        el(5, "text", "River wraiths.", page=1),
    )
    out = chunks_of(parsed)
    assert [c.chunk_id for c in out] == ["delta-crossing-000", "delta-crossing-001"]
    assert out[0].chunk_text == "The Delta Crossing › The River\n\nWide and cold.\n\nIt runs in layers."
    assert out[1].chunk_text.startswith("The Delta Crossing › Dangers\n\n")
    assert (out[0].page, out[1].page) == (1, 2)
    assert {c.location_id for c in out} == {"delta-crossing"}


def test_text_before_any_section_belongs_to_title():
    out = chunks_of(doc(el(0, "title", "Intro"), el(1, "text", "Opening words.")))
    assert out[0].chunk_text == "Intro\n\nOpening words."


def test_page_furniture_is_skipped_and_empty_sections_dropped():
    out = chunks_of(doc(
        el(0, "page_header", "Databricks Adventure"),
        el(1, "title", "T"),
        el(2, "section_header", "Empty"),
        el(3, "section_header", "Full"),
        el(4, "page_number", "1"),
        el(5, "text", "Body."),
    ))
    assert len(out) == 1
    assert out[0].chunk_text == "T › Full\n\nBody."


def test_long_sections_split_at_element_boundaries_keeping_heading():
    para = "x" * 700
    out = chunks_of(doc(el(0, "title", "T"), el(1, "section_header", "Long"),
                        *[el(i, "text", para) for i in range(2, 7)]))
    assert len(out) > 1
    assert all(len(c.chunk_text) <= MAX_CHUNK_CHARS for c in out)
    assert all(c.chunk_text.startswith("T › Long\n\n") for c in out)


def test_chunk_ids_are_deterministic():
    parsed = doc(el(0, "title", "T"), el(1, "text", "a"), el(2, "section_header", "S"), el(3, "text", "b"))
    assert chunks_of(parsed) == chunks_of(parsed)


def test_element_without_bbox_defaults_to_page_one():
    out = chunks_of(doc({"id": 0, "type": "title", "content": "T"}, {"id": 1, "type": "text", "content": "b"}))
    assert out[0].page == 1
