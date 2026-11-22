"""Database access for Show-book-kar.

The only module that knows how to reach PostgreSQL. Connections are created per
unit of work and always closed; nothing is committed or rolled back outside
:func:`transaction`, which does both.

Contracts (see ``backend/README.md``):
  * driver is psycopg2;
  * configuration is the flat ``DB_*`` set from ``.env``;
  * every statement is parameterised with ``%s`` placeholders - user input is
    never formatted into SQL text;
  * rows come back as mappings (``RealDictCursor``).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def config() -> dict:
    """Connection settings from the environment (flat ``DB_*`` variables)."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "show-book-kar"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def connect():
    """Open one non-autocommit connection."""
    settings = config()
    if not settings["password"]:
        raise RuntimeError(
            "DB_PASSWORD is not set. Copy .env.example to .env and fill it in."
        )
    conn = psycopg2.connect(
        connect_timeout=5, cursor_factory=RealDictCursor, **settings
    )
    conn.autocommit = False
    return conn


@contextmanager
def transaction():
    """Yield a cursor inside one transaction; commit on success, rollback on error.

    Multi-statement writes (hold, pay, cancel) belong in a single call to this
    context manager: psycopg2's ``with conn`` commits when the block exits
    normally and rolls back when any exception escapes it.
    """
    conn = connect()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple | None = None) -> list:
    """Run a query and return every row as a mapping (empty list when no rows)."""
    with transaction() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | None = None):
    """Run a query and return the first row as a dict, or ``None``."""
    with transaction() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row is not None else None


def check_connection() -> dict:
    """Prove the app can reach the database and that the schema is loaded."""
    with transaction() as cur:
        cur.execute(
            """
            SELECT current_database()                          AS database_name,
                   current_setting('server_version')           AS server_version,
                   NOW()                                       AS server_time,
                   to_regclass('public.shows') IS NOT NULL     AS schema_loaded
            """
        )
        return dict(cur.fetchone())
