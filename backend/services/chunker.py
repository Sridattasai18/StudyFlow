from typing import Generator


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """
    Split text into overlapping word-based chunks.
    Returns list of dicts with 'text' and 'index' keys.
    """
    words = text.split()
    chunks = []
    i = 0
    idx = 0
    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunk_text = " ".join(chunk_words)
        if len(chunk_text.strip()) > 30:  # skip near-empty chunks
            chunks.append({"text": chunk_text, "index": idx})
            idx += 1
        i += chunk_size - overlap
    return chunks
