"""Notes CRUD — get and save per-notebook notes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
from db.database import get_db
from db.models import Note

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteUpdate(BaseModel):
    content: str


@router.get("/{notebook_id}")
async def get_notes(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Note).where(Note.notebook_id == notebook_id))
    note = result.scalar_one_or_none()
    if not note:
        return {"notebook_id": notebook_id, "content": ""}
    return {"notebook_id": notebook_id, "content": note.content, "updatedAt": note.updated_at.isoformat() if note.updated_at else None}


@router.put("/{notebook_id}")
async def save_notes(notebook_id: str, body: NoteUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Note).where(Note.notebook_id == notebook_id))
    note = result.scalar_one_or_none()
    if note:
        note.content = body.content
        note.updated_at = datetime.now(timezone.utc)
    else:
        note = Note(id=str(uuid.uuid4()), notebook_id=notebook_id, content=body.content)
        db.add(note)
    await db.commit()
    return {"notebook_id": notebook_id, "content": note.content}
