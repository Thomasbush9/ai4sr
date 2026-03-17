# webapp/db.py
import sqlite3
from contextlib import contextmanager
import os
from pathlib import Path

try:
    import config
    DB_PATH = str(config.DB_PATH)
except Exception:
    DB_PATH = "data/review.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database using the canonical schema from db/schema.sql."""
    from db.connection import init_db as _init_db
    _init_db()
