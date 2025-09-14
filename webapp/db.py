# webapp/db.py
import sqlite3
from contextlib import contextmanager
import os
from pathlib import Path

try:
    import config
    DB_PATH = str(config.DB_PATH)  # <— use your config DB_PATH
except Exception:
    DB_PATH = "data/review.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Unified schema that includes both core tables and chat tables
UNIFIED_SCHEMA = """
PRAGMA foreign_keys = ON;

-- Core tables (from db/schema.sql)
CREATE TABLE IF NOT EXISTS projects (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS papers (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  -- identifiers
  pmid          TEXT,
  pmcid         TEXT,
  doi           TEXT,

  -- metadata
  title         TEXT NOT NULL,
  abstract      TEXT,
  authors       TEXT,
  year          INTEGER,
  venue         TEXT,          -- your DF's "journal"
  volume        TEXT,
  issue         TEXT,

  -- links
  pubmed_url    TEXT,
  doi_url       TEXT,
  url           TEXT,          -- preferred landing: doi_url or pubmed_url
  pdf_path      TEXT,

  -- screening outcome
  status        TEXT NOT NULL CHECK (status IN ('include','maybe')),
  score         INTEGER CHECK (score BETWEEN 0 AND 100),
  rationale     TEXT,          -- optional explanation

  -- utils
  citations_crossref INTEGER,
  fingerprint   TEXT,
  added_at      TEXT NOT NULL DEFAULT (datetime('now')),

  UNIQUE(project_id, doi),
  UNIQUE(project_id, pmid),
  UNIQUE(project_id, pmcid),
  UNIQUE(project_id, fingerprint)
);

-- FTS (optional)
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
  title, abstract,
  tokenize='porter'
);

CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project_id);
CREATE INDEX IF NOT EXISTS idx_papers_status  ON papers(project_id, status);

-- Chat tables
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
"""

@contextmanager
def get_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()
def init_db():
    with get_db() as db:
        db.executescript(UNIFIED_SCHEMA)
        db.commit()

