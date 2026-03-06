"""
StudyFlow FastAPI Backend — main entry point.
Run with: uvicorn main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db.database import engine
from db.models import Base
from api import notebooks, sources, chat, studio, notes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load the embedding model so first request isn't slow
    from services.embeddings import get_model
    get_model()
    yield
    # Cleanup on shutdown
    await engine.dispose()


app = FastAPI(
    title="StudyFlow API",
    description="Backend for the StudyFlow NotebookLM clone",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(notebooks.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(studio.router)
app.include_router(notes.router)


@app.get("/")
async def health():
    return {"status": "ok", "message": "StudyFlow API is running"}
