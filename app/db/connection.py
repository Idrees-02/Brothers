"""SQLite connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.db.migrations import apply_migrations
from app.db.seed import seed_if_empty


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")


def connect(db_file: str | Path, default_override_password: str = "0000") -> sqlite3.Connection:
    """Open (creating if needed) the database at db_file, applying migrations
    and seeding default data on first run."""
    conn = sqlite3.connect(str(db_file))
    _configure(conn)
    apply_migrations(conn)
    seed_if_empty(conn, default_override_password=default_override_password)
    return conn


@contextmanager
def connect_ctx(db_file: str | Path, default_override_password: str = "0000"):
    conn = connect(db_file, default_override_password=default_override_password)
    try:
        yield conn
    finally:
        conn.close()


def connect_memory() -> sqlite3.Connection:
    """In-memory database for tests - schema applied, no seed data unless
    the caller invokes seed_if_empty itself."""
    conn = sqlite3.connect(":memory:")
    _configure(conn)
    apply_migrations(conn)
    return conn
