"""
ChromaDB vector store — runs in-process, persists to disk.
One ChromaDB collection per notebook, namespaced by notebook_id.
"""
from __future__ import annotations
import chromadb
import logging
from chromadb.config import Settings
from config import settings as app_settings
from services.embeddings import embed_texts, embed_query

logger = logging.getLogger(__name__)

_client: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=app_settings.chroma_persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _collection_name(notebook_id: str) -> str:
    # ChromaDB collection names must be alphanumeric + hyphens, max 63 chars
    # Use full UUID to avoid collisions, truncate if necessary but keep uniqueness
    safe_id = notebook_id.replace('_', '-').replace(' ', '-')
    if len(safe_id) <= 63:
        return f"nb-{safe_id}"
    # If too long, use hash of the full ID to ensure uniqueness
    import hashlib
    hash_suffix = hashlib.md5(notebook_id.encode()).hexdigest()[:8]
    return f"nb-{safe_id[:50]}-{hash_suffix}"


def store_chunks(
    notebook_id: str,
    source_id: str,
    filename: str,
    chunks: list[dict],  # [{"text": ..., "page": ..., "index": ...}]
) -> int:
    if not chunks:
        return 0
    client = get_client()
    collection = client.get_or_create_collection(_collection_name(notebook_id))

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    metadatas = [
        {
            "source_id": source_id,
            "filename": filename,
            "page": c.get("page", 0),
            "chunk_index": c.get("index", i),
        }
        for i, c in enumerate(chunks)
    ]
    ids = [f"{source_id}_{i}" for i in range(len(chunks))]

    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )
    return len(chunks)


def search_chunks(notebook_id: str, query: str, top_k: int = 5) -> list[dict]:
    client = get_client()
    try:
        collection = client.get_collection(_collection_name(notebook_id))
    except Exception as e:
        logger.error(f"ChromaDB error getting collection: {e}", exc_info=True)
        return []  # No sources ingested yet

    try:
        query_embedding = embed_query(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
        )
    except Exception as e:
        logger.error(f"ChromaDB error during search: {e}", exc_info=True)
        return []

    if not results["documents"] or not results["documents"][0]:
        return []

    return [
        {
            "text": doc,
            "filename": meta.get("filename", "Unknown"),
            "page": meta.get("page", 0),
            "source_id": meta.get("source_id", ""),
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def delete_source_chunks(notebook_id: str, source_id: str) -> None:
    client = get_client()
    try:
        collection = client.get_collection(_collection_name(notebook_id))
        collection.delete(where={"source_id": source_id})
    except Exception as e:
        logger.error(f"ChromaDB error: {e}", exc_info=True)


def delete_notebook_collection(notebook_id: str) -> None:
    """Delete the entire ChromaDB collection for a notebook."""
    client = get_client()
    try:
        collection_name = _collection_name(notebook_id)
        client.delete_collection(collection_name)
        logger.info(f"Deleted ChromaDB collection: {collection_name}")
    except Exception as e:
        logger.error(f"Failed to delete ChromaDB collection {collection_name}: {e}", exc_info=True)


def delete_notebook_collection(notebook_id: str) -> None:
    client = get_client()
    try:
        client.delete_collection(_collection_name(notebook_id))
    except Exception as e:
        logger.error(f"ChromaDB error: {e}", exc_info=True)
