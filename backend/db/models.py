import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


def now_utc():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Notebook")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    sources: Mapped[list["Source"]] = relationship("Source", back_populates="notebook", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship("ChatSession", back_populates="notebook", cascade="all, delete-orphan")
    studio_outputs: Mapped[list["StudioOutput"]] = relationship("StudioOutput", back_populates="notebook", cascade="all, delete-orphan")
    notes: Mapped[list["Note"]] = relationship("Note", back_populates="notebook", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    notebook_id: Mapped[str] = mapped_column(String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, url, youtube, text
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing, ready, error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    notebook: Mapped["Notebook"] = relationship("Notebook", back_populates="sources")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    notebook_id: Mapped[str] = mapped_column(String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    notebook: Mapped["Notebook"] = relationship("Notebook", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class StudioOutput(Base):
    __tablename__ = "studio_outputs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    notebook_id: Mapped[str] = mapped_column(String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    output_type: Mapped[str] = mapped_column(String(30), nullable=False)  # study_guide, briefing, flashcards, mindmap
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    notebook: Mapped["Notebook"] = relationship("Notebook", back_populates="studio_outputs")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    notebook_id: Mapped[str] = mapped_column(String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    notebook: Mapped["Notebook"] = relationship("Notebook", back_populates="notes")
