"""Chat endpoint with SSE streaming and citation tracking."""
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from db.database import get_db
from db.models import ChatSession, ChatMessage
from services import rag, llm

router = APIRouter(prefix="/api/chat", tags=["chat"])


from sqlalchemy.orm import selectinload

async def _get_or_create_session(notebook_id: str, db: AsyncSession) -> str:
    """Get the first chat session for a notebook, or create one."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.notebook_id == notebook_id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        session = ChatSession(id=str(uuid.uuid4()), notebook_id=notebook_id)
        db.add(session)
        await db.commit()
    return session.id


class ChatBody(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/{notebook_id}")
async def chat(notebook_id: str, body: ChatBody, db: AsyncSession = Depends(get_db)):
    """Send a message and receive a streamed AI response grounded in notebook sources."""
    session_id = await _get_or_create_session(notebook_id, db)

    # Save user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=body.message,
        citations_json=[],
    )
    db.add(user_msg)
    await db.commit()

    # Retrieve relevant chunks from ChromaDB
    chunks = rag.search_chunks(notebook_id, body.message, top_k=5)

    # Extract citation info
    citations = [
        {"sourceId": c["source_id"], "filename": c["filename"], "page": c["page"]}
        for c in chunks
    ]

    # Stream the response
    assistant_id = str(uuid.uuid4())
    full_response = []

    async def generate():
        nonlocal full_response
        try:
            # Stream text chunks
            for text_chunk in llm.stream_chat_response(body.message, chunks):
                full_response.append(text_chunk)
                # SSE format: data: <json>\n\n
                yield f"data: {json.dumps({'type': 'text', 'content': text_chunk})}\n\n"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred while generating the response.'})}\n\n"
            return

        # After streaming completes, send citations
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Persist assistant message to DB (fire-and-forget pattern)
        import logging
        from db.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as save_db:
                assistant_msg = ChatMessage(
                    id=assistant_id,
                    session_id=session_id,
                    role="assistant",
                    content="".join(full_response),
                    citations_json=citations,
                )
                save_db.add(assistant_msg)
                await save_db.commit()
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save chat history: {e}", exc_info=True)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{notebook_id}/history")
async def get_history(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).where(ChatSession.notebook_id == notebook_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return []

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations_json or [],
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.delete("/{notebook_id}/history", status_code=204)
async def clear_history(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).where(ChatSession.notebook_id == notebook_id)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
