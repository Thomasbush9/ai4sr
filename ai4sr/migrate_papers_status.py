#!/usr/bin/env python3
"""
Migration script to update papers.status constraint to include UNSCREENED.
SQLite doesn't support ALTER TABLE for CHECK constraints, so we need to recreate the table.
"""
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import DB_PATH

def migrate_papers_status():
    """Update papers.status constraint to include UNSCREENED."""
    print(f"Migrating papers.status constraint at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check current constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='papers'")
        old_sql = cursor.fetchone()[0]
        
        if "UNSCREENED" in old_sql:
            print("✓ Constraint already includes UNSCREENED")
            return
        
        print("Backing up existing papers...")
        # Backup all papers
        cursor.execute("SELECT * FROM papers")
        papers_data = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        print(f"  Found {len(papers_data)} papers to backup")
        
        # Backup FTS data
        cursor.execute("SELECT rowid, title, abstract FROM papers_fts")
        fts_data = cursor.fetchall()
        print(f"  Found {len(fts_data)} FTS entries to backup")
        
        # Create new table with updated constraint
        print("Creating new papers table with UNSCREENED status...")
        cursor.execute("""
            CREATE TABLE papers_new (
              id            INTEGER PRIMARY KEY,
              project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              pmid          TEXT,
              pmcid         TEXT,
              doi           TEXT,
              title         TEXT NOT NULL,
              abstract      TEXT,
              authors       TEXT,
              year          INTEGER,
              venue         TEXT,
              volume        TEXT,
              issue         TEXT,
              pubmed_url    TEXT,
              doi_url       TEXT,
              url           TEXT,
              pdf_path      TEXT,
              status        TEXT NOT NULL CHECK (status IN ('include','maybe','UNSCREENED')),
              score         INTEGER CHECK (score BETWEEN 0 AND 100),
              rationale     TEXT,
              citations_crossref INTEGER,
              fingerprint   TEXT,
              added_at      TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE(project_id, doi),
              UNIQUE(project_id, pmid),
              UNIQUE(project_id, pmcid),
              UNIQUE(project_id, fingerprint)
            )
        """)
        
        # Copy data
        print("Copying data to new table...")
        cursor.execute("""
            INSERT INTO papers_new 
            SELECT * FROM papers
        """)
        
        # Drop old table and rename
        print("Replacing old table...")
        cursor.execute("DROP TABLE papers")
        cursor.execute("ALTER TABLE papers_new RENAME TO papers")
        
        # Recreate indexes
        print("Recreating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(project_id, status)")
        
        # Recreate FTS table
        print("Recreating FTS table...")
        cursor.execute("DROP TABLE IF EXISTS papers_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE papers_fts USING fts5(
              title, abstract,
              tokenize='porter'
            )
        """)
        
        # Restore FTS data
        print("Restoring FTS data...")
        for rowid, title, abstract in fts_data:
            cursor.execute(
                "INSERT INTO papers_fts(rowid, title, abstract) VALUES (?, ?, ?)",
                (rowid, title, abstract)
            )
        
        conn.commit()
        print(f"✓ Migration completed successfully. {len(papers_data)} papers migrated.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_papers_status()

