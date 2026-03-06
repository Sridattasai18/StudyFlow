"""Source ingestion endpoints — PDF upload, URL, YouTube, plain text."""
import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, validator
from db.database import get_db
from db.models import Source
from config import settings
from services import rag
from services.ingestion import pdf, url, youtube, text as text_ingestion

router = APIRouter(prefix="/api/sources", tags=["sources"])


async def _ingest_and_store(
    source_id: str,
    notebook_id: str,
    filename: str,
    chunks: list[dict],
    db_session_factory,
):
    """Background task: store chunks in ChromaDB and update source status."""
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            count = rag.store_chunks(notebook_id, source_id, filename, chunks)
            result = await db.execute(select(Source).where(Source.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                source.chunk_count = count
                source.status = "ready"
                await db.commit()
        except Exception as e:
            import logging
            result = await db.execute(select(Source).where(Source.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                source.status = "error"
                await db.commit()
            logging.getLogger(__name__).error(f"Ingestion error for source {source_id}: {e}", exc_info=True)


@router.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    notebook_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    source_id = str(uuid.uuid4())
    save_path = os.path.join(settings.upload_dir, f"{source_id}_{file.filename}")

    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        type="pdf",
        filename=file.filename,
        status="processing",
    )
    db.add(source)
    await db.commit()

    # Extract chunks in background
    try:
        chunks = pdf.extract_pdf(save_path)
    except Exception as e:
        source.status = "error"
        await db.commit()
        raise HTTPException(status_code=422, detail=f"Failed to extract PDF: {e}")

    background_tasks.add_task(
        _ingest_and_store, source_id, notebook_id, file.filename, chunks, None
    )
    return {"id": source_id, "filename": file.filename, "status": "processing"}


class UrlSourceBody(BaseModel):
    notebook_id: str
    url: str

    @validator('url')
    def validate_url(cls, v):
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError('Invalid URL format')
        if parsed.scheme not in ['http', 'https']:
            raise ValueError('URL must use http or https scheme')
        return v


@router.post("/url")
async def add_url_source(body: UrlSourceBody, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    source_id = str(uuid.uuid4())
    hostname = body.url.split("/")[2] if "//" in body.url else body.url[:50]

    source = Source(
        id=source_id,
        notebook_id=body.notebook_id,
        type="url",
        filename=hostname,
        url=body.url,
        status="processing",
    )
    db.add(source)
    await db.commit()

    try:
        chunks = url.extract_url(body.url)
    except Exception as e:
        source.status = "error"
        await db.commit()
        raise HTTPException(status_code=422, detail=f"Failed to scrape URL: {e}")

    background_tasks.add_task(
        _ingest_and_store, source_id, body.notebook_id, hostname, chunks, None
    )
    return {"id": source_id, "filename": hostname, "url": body.url, "status": "processing"}


class YoutubeSourceBody(BaseModel):
    notebook_id: str
    url: str


@router.post("/youtube")
async def add_youtube_source(body: YoutubeSourceBody, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    source_id = str(uuid.uuid4())
    filename = f"YouTube: {body.url[-20:]}"

    source = Source(
        id=source_id,
        notebook_id=body.notebook_id,
        type="youtube",
        filename=filename,
        url=body.url,
        status="processing",
    )
    db.add(source)
    await db.commit()

    try:
        chunks = youtube.extract_youtube(body.url)
    except Exception as e:
        source.status = "error"
        await db.commit()
        raise HTTPException(status_code=422, detail=f"Failed to fetch YouTube transcript: {e}")

    background_tasks.add_task(
        _ingest_and_store, source_id, body.notebook_id, filename, chunks, None
    )
    return {"id": source_id, "filename": filename, "url": body.url, "status": "processing"}


class TextSourceBody(BaseModel):
    notebook_id: str
    content: str
    title: str = "Pasted Text"


@router.post("/text")
async def add_text_source(body: TextSourceBody, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    source_id = str(uuid.uuid4())

    source = Source(
        id=source_id,
        notebook_id=body.notebook_id,
        type="text",
        filename=body.title,
        status="processing",
    )
    db.add(source)
    await db.commit()

    chunks = text_ingestion.extract_text(body.content)
    background_tasks.add_task(
        _ingest_and_store, source_id, body.notebook_id, body.title, chunks, None
    )
    return {"id": source_id, "filename": body.title, "status": "processing"}


@router.get("/{source_id}")
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"id": source.id, "filename": source.filename, "type": source.type, "status": source.status, "chunkCount": source.chunk_count}


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    notebook_id = source.notebook_id
    await db.delete(source)
    await db.commit()
    rag.delete_source_chunks(notebook_id, source_id)
