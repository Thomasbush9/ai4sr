PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS papers (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_id     TEXT,
  doi           TEXT,
  title         TEXT NOT NULL,
  abstract      TEXT,
  authors       TEXT,
  year          INTEGER,
  venue         TEXT,
  url           TEXT,
  pdf_path      TEXT,
  status        TEXT NOT NULL CHECK (status IN ('include','maybe')),
  score         INTEGER CHECK (score BETWEEN 0 AND 100),
  fingerprint   TEXT,
  added_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, doi),
  UNIQUE(project_id, source_id),
  UNIQUE(project_id, fingerprint)
);

-- Optional but nice for searching titles/abstracts
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
  title, abstract, content='',
  tokenize='porter'
);

CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project_id);
CREATE INDEX IF NOT EXISTS idx_papers_status  ON papers(project_id, status);

