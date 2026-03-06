"""Plain text / markdown ingestion."""
from services.chunker import chunk_text


def extract_text(content: str) -> list[dict]:
    """Chunk raw text content. Returns list of chunk dicts."""
    chunks = chunk_text(content)
    return [{"text": c["text"], "page": 0, "index": c["index"]} for c in chunks]
