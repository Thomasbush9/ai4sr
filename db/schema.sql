PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Store only include/maybe for now
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

-- Conversations table for chat history
CREATE TABLE IF NOT EXISTS conversations (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Messages table for storing conversation messages
CREATE TABLE IF NOT EXISTS messages (
  id              INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);

