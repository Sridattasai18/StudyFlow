"""URL ingestion using BeautifulSoup — scrapes article text from a webpage."""
import requests
from bs4 import BeautifulSoup
from services.chunker import chunk_text


def extract_url(url: str) -> list[dict]:
    """Fetch a URL and extract readable text. Returns chunks."""
    headers = {"User-Agent": "Mozilla/5.0 (StudyFlow Research Bot)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove scripts and styles
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Prefer article/main content
    content = soup.find("article") or soup.find("main") or soup.body
    raw_text = content.get_text(separator=" ", strip=True) if content else ""

    if not raw_text.strip():
        raise ValueError("Could not extract readable text from this URL.")

    chunks = chunk_text(raw_text)
    return [{"text": c["text"], "page": 0, "index": c["index"]} for c in chunks]
