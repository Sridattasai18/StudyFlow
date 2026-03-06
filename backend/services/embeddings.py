"""
Global sentence-transformers model loaded ONCE at startup.
Embedding runs fully locally — no API calls, no cost.
Model: all-MiniLM-L6-v2 (~80MB download on first run)
"""
from __future__ import annotations
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Loading embedding model (first time only)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    try:
        model = get_model()
        return model.encode(texts, show_progress_bar=False).tolist()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to embed texts: {e}", exc_info=True)
        # Return zero vectors as fallback to prevent crashes
        return [[0.0] * 384 for _ in texts]  # 384 is the dimension of all-MiniLM-L6-v2


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
