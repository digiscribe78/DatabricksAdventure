"""Turn ai_parse_document output into retrieval chunks, one per section, with heading paths."""

from dataclasses import dataclass

MAX_CHUNK_CHARS = 1800
SKIP_TYPES = {"page_header", "page_footer", "page_number"}
_SEP = " › "


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    chunk_text: str
    doc_type: str
    location_id: str
    source: str
    page: int


def _page(element: dict) -> int:
    bbox = element.get("bbox") or []
    return (bbox[0].get("page_id", 0) if bbox else 0) + 1


def _split_words(text: str, limit: int) -> list[str]:
    """Split one over-long element on word boundaries so each piece fits ``limit`` characters."""
    pieces, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > limit:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_document(parsed: dict, source: str, doc_type: str, location_id: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    title: str | None = None
    path: list[str] = []
    body: list[str] = []
    first_page = 1

    def flush() -> None:
        nonlocal body
        if body:
            text = _SEP.join(path) + "\n\n" + "\n\n".join(body)
            chunks.append(Chunk(f"{source}-{len(chunks):03d}", text, doc_type, location_id, source, first_page))
        body = []

    for element in parsed.get("document", {}).get("elements", []):
        kind, content = element.get("type"), (element.get("content") or "").strip()
        if kind in SKIP_TYPES or not content:
            continue
        if kind == "title":
            flush()
            title, path = content, [content]
        elif kind == "section_header":
            flush()
            path = [title, content] if title else [content]
        else:
            prefix_len = len(_SEP.join(path)) + 2
            limit = MAX_CHUNK_CHARS - prefix_len
            for piece in _split_words(content, limit) if len(content) > limit else [content]:
                if body and prefix_len + len("\n\n".join([*body, piece])) > MAX_CHUNK_CHARS:
                    flush()
                if not body:
                    first_page = _page(element)
                body.append(piece)
    flush()
    return chunks
