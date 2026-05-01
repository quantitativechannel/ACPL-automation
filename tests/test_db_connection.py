from __future__ import annotations

import sqlite3

import pytest

from src.db.connection import create_connection, db_connection


def test_create_connection_enables_foreign_keys_and_row_factory() -> None:
    conn = create_connection()
    try:
        fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1
        assert conn.row_factory is sqlite3.Row
    finally:
        conn.close()


def test_db_connection_commits_on_success(tmp_path) -> None:
    db_path = tmp_path / "commit.sqlite"

    with db_connection(str(db_path)) as conn:
        conn.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO entries (value) VALUES (?)", ("ok",))

    with create_connection(str(db_path)) as verify_conn:
        count = verify_conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        assert count == 1


def test_db_connection_rolls_back_on_error(tmp_path) -> None:
    db_path = tmp_path / "rollback.sqlite"

    with db_connection(str(db_path)) as conn:
        conn.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, value TEXT)")

    with pytest.raises(RuntimeError):
        with db_connection(str(db_path)) as conn:
            conn.execute("INSERT INTO entries (value) VALUES (?)", ("nope",))
            raise RuntimeError("boom")

    with create_connection(str(db_path)) as verify_conn:
        count = verify_conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        assert count == 0


def test_db_connection_closes_safely(tmp_path) -> None:
    db_path = tmp_path / "closed.sqlite"

    with db_connection(str(db_path)) as conn:
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
