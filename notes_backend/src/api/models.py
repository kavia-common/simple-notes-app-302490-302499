from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.api.db import db_error_handler, get_database_url

Base = declarative_base()


class NoteORM(Base):
    """
    SQLAlchemy ORM model for the `notes` table.
    """

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# Lazily initialize SQLAlchemy engine and sessionmaker so DB URL can be loaded at runtime.
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            future=True,
        )
    return _engine


def get_session_factory():
    """
    Get (and lazily create) the SQLAlchemy session factory (SessionLocal).
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_get_engine(),
            class_=Session,
        )
    return _SessionLocal


def init_db() -> None:
    """
    Initialize the database by creating the `notes` table if it does not exist.

    This uses SQLAlchemy's metadata to emit the appropriate DDL via the configured engine.
    """
    with db_error_handler():
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)


# PUBLIC_INTERFACE
class NoteBase(BaseModel):
    """Base schema shared by note create and update operations."""

    title: str = Field(..., description="Title of the note", max_length=255)
    content: str = Field(..., description="Body content of the note")


# PUBLIC_INTERFACE
class NoteCreate(NoteBase):
    """Schema for creating a note."""
    pass


# PUBLIC_INTERFACE
class NoteUpdate(BaseModel):
    """Schema for updating an existing note."""

    title: Optional[str] = Field(
        None, description="New title for the note", max_length=255
    )
    content: Optional[str] = Field(
        None,
        description="New body content for the note",
    )


# PUBLIC_INTERFACE
class NoteOut(NoteBase):
    """Schema returned when reading a note."""

    id: int = Field(..., description="Unique identifier of the note")
    created_at: datetime = Field(..., description="Timestamp when the note was created")
    updated_at: datetime = Field(..., description="Timestamp when the note was last updated")

    class Config:
        from_attributes = True


# PUBLIC_INTERFACE
def get_db_session() -> Session:
    """Provide a new SQLAlchemy Session. Caller is responsible for closing it."""
    SessionLocal = get_session_factory()
    return SessionLocal()


# PUBLIC_INTERFACE
def list_notes() -> List[NoteOut]:
    """Return all notes ordered by creation time descending."""
    with db_error_handler():
        db = get_db_session()
        try:
            query = db.query(NoteORM).order_by(NoteORM.created_at.desc())
            results = query.all()
            return [NoteOut.model_validate(note) for note in results]
        finally:
            db.close()


# PUBLIC_INTERFACE
def create_note(note_in: NoteCreate) -> NoteOut:
    """Create a new note and return it."""
    with db_error_handler():
        db = get_db_session()
        try:
            note = NoteORM(
                title=note_in.title,
                content=note_in.content,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(note)
            db.commit()
            db.refresh(note)
            return NoteOut.model_validate(note)
        finally:
            db.close()


# PUBLIC_INTERFACE
def get_note(note_id: int) -> Optional[NoteOut]:
    """Fetch a note by ID, returning None if not found."""
    with db_error_handler():
        db = get_db_session()
        try:
            note = db.get(NoteORM, note_id)
            if note is None:
                return None
            return NoteOut.model_validate(note)
        finally:
            db.close()


# PUBLIC_INTERFACE
def update_note(note_id: int, note_in: NoteUpdate) -> Optional[NoteOut]:
    """Update an existing note and return the updated entity, or None if not found."""
    with db_error_handler():
        db = get_db_session()
        try:
            note = db.get(NoteORM, note_id)
            if note is None:
                return None

            if note_in.title is not None:
                note.title = note_in.title
            if note_in.content is not None:
                note.content = note_in.content
            note.updated_at = datetime.utcnow()

            db.add(note)
            db.commit()
            db.refresh(note)
            return NoteOut.model_validate(note)
        finally:
            db.close()


# PUBLIC_INTERFACE
def delete_note(note_id: int) -> bool:
    """Delete a note by ID. Returns True if deleted, False if not found."""
    with db_error_handler():
        db = get_db_session()
        try:
            note = db.get(NoteORM, note_id)
            if note is None:
                return False
            db.delete(note)
            db.commit()
            return True
        finally:
            db.close()
