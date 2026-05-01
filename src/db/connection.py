from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


def create_connection(db_path: str = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection configured for safe per-use lifecycle."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection(db_path: str = ":memory:") -> Iterator[sqlite3.Connection]:
    """Open a fresh SQLite connection, then commit/rollback and close safely."""
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
