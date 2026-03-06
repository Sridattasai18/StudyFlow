"""
Gemini API wrapper for chat (RAG) and studio output generation.
Uses google-generativeai SDK with gemini-1.5-flash model.
"""
from __future__ import annotations
import json
import re
from typing import Generator
import google.generativeai as genai
from config import settings

_model = None


def get_model():
    global _model
    if _model is None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required but not set")
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


# ─── Grounding system prompt ───────────────────────────────────────────────────
CHAT_SYSTEM = """You are a research assistant for StudyFlow. Your job is to answer
the user's question ONLY using the source documents provided below.

Rules:
1. Only use information from the provided sources. Never use outside knowledge.
2. For every factual claim, add a citation: [Source: <filename>, Page <page>]
3. If the answer is not in the sources, say exactly: "I couldn't find this in your sources."
4. Be concise. Prefer bullet points for multi-part answers.
5. Never make up citations or page numbers.

--- SOURCES ---
{chunks}
--- END SOURCES ---
"""


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "(No sources have been added to this notebook yet.)"
    return "\n\n".join(
        f"[Source: {c['filename']}, Page {c['page']}]\n{c['text']}" for c in chunks
    )


def generate_chat_response(query: str, chunks: list[dict]) -> str:
    """Non-streaming chat response (used for simple cases)."""
    model = get_model()
    prompt = CHAT_SYSTEM.format(chunks=_format_chunks(chunks))
    response = model.generate_content(
        [{"role": "user", "parts": [prompt + "\n\nUser question: " + query]}]
    )
    return response.text


def stream_chat_response(query: str, chunks: list[dict]) -> Generator[str, None, None]:
    """Streaming chat — yields text chunks as they arrive from Gemini."""
    model = get_model()
    prompt = CHAT_SYSTEM.format(chunks=_format_chunks(chunks))
    full_prompt = prompt + "\n\nUser question: " + query

    response = model.generate_content(full_prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


def generate_studio_output(output_type: str, chunks: list[dict]) -> dict:
    """Generate structured studio output (study guide, briefing, flashcards, mindmap)."""
    model = get_model()
    source_text = _format_chunks(chunks)
    prompt = _studio_prompt(output_type, source_text)
    response = model.generate_content(prompt)
    return _parse_studio_response(output_type, response.text)


def _studio_prompt(output_type: str, source_text: str) -> str:
    base = f"Based on these source documents:\n\n{source_text}\n\n"

    if output_type == "study_guide":
        return base + """Generate a structured study guide with these sections:
1. Key Concepts (5-8 bullet points with brief definitions)
2. Common Challenges or Pitfalls
3. Essay / Discussion Questions (3-5 open-ended questions)

Return as JSON:
{"sections": [{"title": "Key Concepts", "items": ["..."]}, ...]}
Only return valid JSON, no markdown fences."""

    elif output_type == "briefing":
        return base + """Write an executive briefing document with:
1. Overview (2-3 sentences)
2. Key Points (4-6 bullet points)
3. Strategic Recommendation (1-2 sentences)

Return as JSON:
{"overview": "...", "key_points": ["..."], "recommendation": "..."}
Only return valid JSON, no markdown fences."""

    elif output_type == "flashcards":
        return base + """Generate 8 flashcard Q&A pairs and 4 multiple-choice quiz questions.

Return as JSON:
{"flashcards": [{"front": "...", "back": "..."}], "quiz": [{"question": "...", "options": ["A)...", "B)...", "C)...", "D)..."], "answer": "A"}]}
Only return valid JSON, no markdown fences."""

    elif output_type == "mindmap":
        return base + """Extract a mind map with 1 central topic, 5-8 main branches, and 2-3 sub-topics each.

Return as JSON:
{"central_topic": "...", "nodes": [{"id": "1", "label": "...", "parent": null}, {"id": "2", "label": "...", "parent": "1"}]}
Node with parent=null is the center. Only return valid JSON, no markdown fences."""

    return base + "Summarize the key information."


def _parse_studio_response(output_type: str, text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences if present."""
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Fallback: return raw text wrapped in a dict
        return {"raw": text, "error": "Could not parse structured output"}
