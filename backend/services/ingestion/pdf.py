"""PDF ingestion using PyMuPDF — extracts text with page numbers."""
import fitz  # PyMuPDF
from services.chunker import chunk_text


def extract_pdf(filepath: str) -> list[dict]:
    """Extract and chunk text from a PDF file. Returns chunks with page numbers."""
    doc = fitz.open(filepath)
    all_chunks = []
    global_index = 0

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if not text.strip():
            continue
        page_chunks = chunk_text(text)
        for chunk in page_chunks:
            all_chunks.append({
                "text": chunk["text"],
                "page": page_num,
                "index": global_index,
            })
            global_index += 1

    doc.close()
    return all_chunks
