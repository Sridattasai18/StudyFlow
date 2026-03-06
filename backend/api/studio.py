"""Studio output generation endpoints — study guide, briefing, flashcards, mindmap."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from db.database import get_db
from db.models import StudioOutput
from services import rag, llm

router = APIRouter(prefix="/api/studio", tags=["studio"])

VALID_TYPES = {"study_guide", "briefing", "flashcards", "mindmap"}


@router.get("/{notebook_id}")
async def list_outputs(notebook_id: str, db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 20):
    """Return all cached studio outputs for a notebook."""
    result = await db.execute(
        select(StudioOutput)
        .where(StudioOutput.notebook_id == notebook_id)
        .order_by(StudioOutput.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    outputs = result.scalars().all()
    return {
        o.output_type: {
            "id": o.id,
            "outputType": o.output_type,
            "contentJson": o.content_json,
            "createdAt": o.created_at.isoformat() if o.created_at else None,
        }
        for o in outputs
    }


async def _generate_output(notebook_id: str, output_type: str, db: AsyncSession) -> dict:
    chunks = rag.search_chunks(notebook_id, output_type.replace("_", " "), top_k=10)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No sources found in this notebook. Add sources before generating studio outputs.",
        )

    content = llm.generate_studio_output(output_type, chunks)

    # Delete previous cached output of same type
    await db.execute(
        delete(StudioOutput).where(
            StudioOutput.notebook_id == notebook_id,
            StudioOutput.output_type == output_type,
        )
    )

    # Save new output
    output = StudioOutput(
        id=str(uuid.uuid4()),
        notebook_id=notebook_id,
        output_type=output_type,
        content_json=content,
    )
    db.add(output)
    await db.commit()
    return content


@router.post("/{notebook_id}/study-guide")
async def generate_study_guide(notebook_id: str, db: AsyncSession = Depends(get_db)):
    content = await _generate_output(notebook_id, "study_guide", db)
    return {"outputType": "study_guide", "content": content}


@router.post("/{notebook_id}/briefing")
async def generate_briefing(notebook_id: str, db: AsyncSession = Depends(get_db)):
    content = await _generate_output(notebook_id, "briefing", db)
    return {"outputType": "briefing", "content": content}


@router.post("/{notebook_id}/flashcards")
async def generate_flashcards(notebook_id: str, db: AsyncSession = Depends(get_db)):
    content = await _generate_output(notebook_id, "flashcards", db)
    return {"outputType": "flashcards", "content": content}


@router.post("/{notebook_id}/mindmap")
async def generate_mindmap(notebook_id: str, db: AsyncSession = Depends(get_db)):
    content = await _generate_output(notebook_id, "mindmap", db)
    return {"outputType": "mindmap", "content": content}
