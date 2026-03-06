"""Notebook CRUD endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from db.database import get_db
from db.models import Notebook, Source
from services.rag import delete_notebook_collection
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


class NotebookCreate(BaseModel):
    name: str = "Untitled Notebook"
    description: str | None = None


class NotebookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


def notebook_to_dict(nb: Notebook) -> dict:
    return {
        "id": nb.id,
        "name": nb.name,
        "description": nb.description,
        "createdAt": nb.created_at.isoformat() if nb.created_at else None,
        "updatedAt": nb.updated_at.isoformat() if nb.updated_at else None,
        "sources": [
            {
                "id": s.id,
                "filename": s.filename,
                "type": s.type,
                "url": s.url,
                "status": s.status,
                "chunkCount": s.chunk_count,
                "createdAt": s.created_at.isoformat() if s.created_at else None,
            }
            for s in (nb.sources or [])
        ],
    }


def _nb_query():
    """Base query with eager-loaded sources to avoid MissingGreenlet."""
    return select(Notebook).options(selectinload(Notebook.sources))


@router.get("")
async def list_notebooks(db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 50):
    result = await db.execute(_nb_query().order_by(Notebook.created_at.desc()).offset(skip).limit(limit))
    notebooks = result.scalars().all()
    return [notebook_to_dict(nb) for nb in notebooks]


@router.post("", status_code=201)
async def create_notebook(body: NotebookCreate, db: AsyncSession = Depends(get_db)):
    nb = Notebook(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
    )
    db.add(nb)
    await db.commit()
    # Refetch with eager load
    result = await db.execute(_nb_query().where(Notebook.id == nb.id))
    nb = result.scalar_one()
    return notebook_to_dict(nb)


@router.get("/{notebook_id}")
async def get_notebook(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_nb_query().where(Notebook.id == notebook_id))
    nb = result.scalar_one_or_none()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook_to_dict(nb)


@router.delete("/{notebook_id}", status_code=204)
async def delete_notebook(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_nb_query().where(Notebook.id == notebook_id))
    nb = result.scalar_one_or_none()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    # Delete ChromaDB collection first
    delete_notebook_collection(notebook_id)
    
    # Delete from database (cascade will handle related records)
    await db.delete(nb)
    await db.commit()


@router.delete("/{notebook_id}", status_code=204)
async def delete_notebook(notebook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Notebook).where(Notebook.id == notebook_id))
    nb = result.scalar_one_or_none()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    await db.delete(nb)
    await db.commit()
    delete_notebook_collection(notebook_id)

