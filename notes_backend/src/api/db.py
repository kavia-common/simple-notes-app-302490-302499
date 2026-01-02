import os
import re
import subprocess
from contextlib import contextmanager
from typing import Generator, Optional

from fastapi import HTTPException


def _load_raw_psql_command() -> str:
    """
    Load the base `psql` connection command from the shared database container.

    The PostgreSQL container exposes a `db_connection.txt` file at:
    ../simple-notes-app-302490-302500/database/db_connection.txt

    That file contains something like:
        psql postgresql://user:password@host:port/dbname
    """
    # Compute path relative to this file's location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_conn_path = os.path.join(
        current_dir,
        "..",
        "..",
        "..",
        "simple-notes-app-302490-302500",
        "database",
        "db_connection.txt",
    )

    try:
        with open(db_conn_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Database connection file db_connection.txt not found. "
            "Ensure the database container is configured correctly."
        ) from exc

    if not content.startswith("psql "):
        raise RuntimeError(
            "Unexpected format in db_connection.txt. Expected line starting with 'psql '."
        )

    return content


def _extract_sqlalchemy_url(psql_command: str) -> str:
    """
    Extract the PostgreSQL SQLAlchemy URL from a `psql` command string.

    Example:
        'psql postgresql://user:pwd@host:port/db' -> 'postgresql+psycopg2://user:pwd@host:port/db'
    """
    match = re.search(r"(postgresql://[^\s]+)", psql_command)
    if not match:
        raise RuntimeError("Could not extract PostgreSQL URL from db_connection.txt.")

    base_url = match.group(1)
    # Use psycopg2 driver for SQLAlchemy sync engine
    if base_url.startswith("postgresql://"):
        return base_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    raise RuntimeError("Unsupported PostgreSQL URL format in db_connection.txt.")


# Lazily initialized SQLAlchemy engine to avoid issues if the DB is not yet up
_SQLALCHEMY_DATABASE_URL: Optional[str] = None


def get_database_url() -> str:
    """
    Resolve and cache the SQLAlchemy-compatible PostgreSQL URL.
    """
    global _SQLALCHEMY_DATABASE_URL
    if _SQLALCHEMY_DATABASE_URL is None:
        raw_psql = _load_raw_psql_command()
        _SQLALCHEMY_DATABASE_URL = _extract_sqlalchemy_url(raw_psql)
    return _SQLALCHEMY_DATABASE_URL


def run_psql_command(sql: str) -> None:
    """
    Execute a single SQL statement using the `psql` CLI as required by the environment.

    This function respects the requirement to send only one SQL statement at a time
    via `psql -c "SQL_STATEMENT"`.

    Args:
        sql: A single SQL statement to execute.

    Raises:
        RuntimeError: If the command fails or `psql` returns a non-zero exit code.
    """
    raw_psql = _load_raw_psql_command()
    # raw_psql is something like: "psql postgresql://user:pwd@host:port/db"
    # We append -c "SQL"
    command = f'{raw_psql} -c "{sql}"'

    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Error executing psql command: {exc}") from exc

    if completed.returncode != 0:
        raise RuntimeError(
            f"psql command failed with code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )


@contextmanager
def db_error_handler() -> Generator[None, None, None]:
    """
    Context manager to convert generic DB errors into HTTP 500 responses.

    This is used in route handlers that call low-level DB utilities.
    """
    try:
        yield
    except HTTPException:
        # Let FastAPI HTTP errors bubble up unchanged
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {exc}",
        ) from exc
