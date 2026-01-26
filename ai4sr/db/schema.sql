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
  status        TEXT NOT NULL CHECK (status IN ('include','maybe','UNSCREENED','excluded')),
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

-- PICO table for storing review questions
CREATE TABLE IF NOT EXISTS pico (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  population    TEXT NOT NULL,
  intervention  TEXT,
  comparison    TEXT,
  outcome       TEXT,
  study_design  TEXT,
  extra_terms   TEXT,          -- JSON array
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pico_project ON pico(project_id);

-- PICO expansion results
CREATE TABLE IF NOT EXISTS pico_expansions (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  question_summary TEXT NOT NULL,
  pubmed_query    TEXT NOT NULL,
  openalex_query  TEXT NOT NULL,
  pico_keywords   TEXT NOT NULL,  -- JSON object
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pico_expansions_project ON pico_expansions(project_id);

-- Ingestion logs for corpus generation
CREATE TABLE IF NOT EXISTS review_ingestion_logs (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  pubmed_query    TEXT,
  openalex_query  TEXT,
  pubmed_count    INTEGER DEFAULT 0,
  openalex_count  INTEGER DEFAULT 0,
  total_unique    INTEGER DEFAULT 0,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ingestion_logs_project ON review_ingestion_logs(project_id);

-- Screening labels table for active learning
CREATE TABLE IF NOT EXISTS screening_labels (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  paper_id      INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  label         TEXT NOT NULL CHECK (label IN ('INCLUDE','EXCLUDE')),
  timestamp     TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_screening_labels_project ON screening_labels(project_id);
CREATE INDEX IF NOT EXISTS idx_screening_labels_paper ON screening_labels(paper_id);
CREATE INDEX IF NOT EXISTS idx_screening_labels_project_paper ON screening_labels(project_id, paper_id);

-- Agent summaries table for structured review summaries
CREATE TABLE IF NOT EXISTS agent_summaries (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  paper_id        INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  population      TEXT,
  intervention    TEXT,
  comparator      TEXT,
  outcomes        TEXT,
  main_findings   TEXT,
  sample_size     TEXT,
  notes           TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_summaries_project ON agent_summaries(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_summaries_paper ON agent_summaries(paper_id);

-- Project agent overview table for global synthesis
CREATE TABLE IF NOT EXISTS project_agent_overview (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  overview_json   TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_agent_overview_project ON project_agent_overview(project_id);
