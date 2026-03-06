"""YouTube transcript ingestion using youtube-transcript-api."""
import re
from youtube_transcript_api import YouTubeTranscriptApi
from services.chunker import chunk_text


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def extract_youtube(url: str) -> list[dict]:
    """Fetch YouTube transcript and return chunks."""
    video_id = _extract_video_id(url)
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

    # Join all transcript segments into one text
    full_text = " ".join(entry["text"] for entry in transcript_list)

    if not full_text.strip():
        raise ValueError("No transcript found for this YouTube video.")

    chunks = chunk_text(full_text)
    return [{"text": c["text"], "page": 0, "index": c["index"]} for c in chunks]
