from typing import List

from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.models import (
    NoteCreate,
    NoteOut,
    NoteUpdate,
    create_note,
    delete_note,
    get_note,
    init_db,
    list_notes,
    update_note,
)

app = FastAPI(
    title="Simple Notes API",
    description=(
        "Backend service for a Simple Notes App. "
        "Provides CRUD operations for notes with title and content fields."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and service status.",
        },
        {
            "name": "notes",
            "description": "Operations for creating, reading, updating, and deleting notes.",
        },
        {
            "name": "websocket",
            "description": "Reserved for future real-time features (not used yet).",
        },
    ],
)

# Configure CORS for React frontend at port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# PUBLIC_INTERFACE
@app.on_event("startup")
def on_startup() -> None:
    """
    Initialize application resources on startup.

    - Ensures the PostgreSQL `notes` table exists using SQLAlchemy metadata.
    """
    init_db()


# PUBLIC_INTERFACE
@app.get(
    "/",
    tags=["health"],
    summary="Health Check",
    description="Simple health check endpoint to verify the API is responsive.",
)
def health_check():
    """Return a simple health status payload."""
    return {"message": "Healthy"}


# Helper dependency for path parameter validation with documentation.
class NoteIdPath(BaseModel):
    """Pydantic model for documenting the note ID path parameter."""

    note_id: int = Field(..., description="Unique identifier of the note", ge=1)


def get_note_id(
    note_id: int = Path(..., description="Unique identifier of the note", ge=1),
) -> int:
    """
    Dependency for validating the `note_id` path parameter.

    This keeps path parameter validation consistent across endpoints.
    """
    return note_id


# PUBLIC_INTERFACE
@app.get(
    "/notes",
    response_model=List[NoteOut],
    tags=["notes"],
    summary="List notes",
    description="Retrieve all notes, ordered by creation time descending.",
)
def list_notes_endpoint() -> List[NoteOut]:
    """
    List all notes stored in the database.

    Returns:
        A list of notes, each containing `id`, `title`, `content`, `created_at`, and `updated_at`.
    """
    return list_notes()


# PUBLIC_INTERFACE
@app.post(
    "/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
    tags=["notes"],
    summary="Create note",
    description="Create a new note with a title and content.",
)
def create_note_endpoint(note_in: NoteCreate) -> NoteOut:
    """
    Create a new note.

    Args:
        note_in: JSON body containing `title` and `content`.

    Returns:
        The newly created note with its unique `id` and timestamps.
    """
    return create_note(note_in)


# PUBLIC_INTERFACE
@app.get(
    "/notes/{note_id}",
    response_model=NoteOut,
    tags=["notes"],
    summary="Get note by ID",
    description="Retrieve a single note by its unique identifier.",
)
def get_note_endpoint(note_id: int = Depends(get_note_id)) -> NoteOut:
    """
    Retrieve a single note.

    Args:
        note_id: Path parameter for the note's unique identifier.

    Returns:
        The requested note.

    Raises:
        HTTPException 404: If the note is not found.
    """
    note = get_note(note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with id {note_id} not found",
        )
    return note


# PUBLIC_INTERFACE
@app.put(
    "/notes/{note_id}",
    response_model=NoteOut,
    tags=["notes"],
    summary="Update note",
    description=(
        "Update the title and/or content of an existing note. "
        "Fields omitted from the request body will remain unchanged."
    ),
)
def update_note_endpoint(
    note_in: NoteUpdate,
    note_id: int = Depends(get_note_id),
) -> NoteOut:
    """
    Update an existing note.

    Args:
        note_id: Path parameter for the note's unique identifier.
        note_in: JSON body with optional `title` and `content` fields.

    Returns:
        The updated note.

    Raises:
        HTTPException 404: If the note is not found.
    """
    updated = update_note(note_id, note_in)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with id {note_id} not found",
        )
    return updated


# PUBLIC_INTERFACE
@app.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["notes"],
    summary="Delete note",
    description="Delete a note by its unique identifier.",
)
def delete_note_endpoint(note_id: int = Depends(get_note_id)) -> JSONResponse:
    """
    Delete a note.

    Args:
        note_id: Path parameter for the note's unique identifier.

    Returns:
        An empty 204 No Content response on success.

    Raises:
        HTTPException 404: If the note is not found.
    """
    deleted = delete_note(note_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with id {note_id} not found",
        )
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


# PUBLIC_INTERFACE
@app.get(
    "/docs/websocket-info",
    tags=["websocket"],
    summary="WebSocket usage (reserved)",
    description=(
        "This endpoint documents how WebSocket connections would be used in the future. "
        "Currently, there are no WebSocket endpoints for this API."
    ),
)
def websocket_info() -> dict:
    """
    Provide documentation for potential future WebSocket usage.

    Returns:
        A simple JSON object explaining that WebSockets are not yet implemented.
    """
    return {
        "message": "No WebSocket endpoints are currently implemented.",
        "note": "This API uses pure HTTP REST endpoints for all operations.",
    }
