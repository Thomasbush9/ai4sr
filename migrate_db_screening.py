#!/usr/bin/env python3
"""
Database migration script for screening labels table and papers.status constraint update.
Adds screening_labels table and extends papers.status to include 'excluded'.
"""
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import DB_PATH


def migrate_database():
    """Apply screening labels schema changes."""
    print(f"Migrating database at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # 1. Create screening_labels table
        if 'screening_labels' not in existing_tables:
            print("Creating screening_labels table...")
            cursor.execute("""
                CREATE TABLE screening_labels (
                  id            INTEGER PRIMARY KEY,
                  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  paper_id      INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                  label         TEXT NOT NULL CHECK (label IN ('INCLUDE','EXCLUDE')),
                  timestamp     TEXT NOT NULL DEFAULT (datetime('now')),
                  UNIQUE(project_id, paper_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screening_labels_project ON screening_labels(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screening_labels_paper ON screening_labels(paper_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_screening_labels_project_paper ON screening_labels(project_id, paper_id)")
            print("✓ Created screening_labels table")
        else:
            print("✓ screening_labels table already exists")
        
        # 2. Update papers.status constraint to include 'excluded'
        print("Updating papers.status constraint to include 'excluded'...")
        
        # Check current constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='papers'")
        result = cursor.fetchone()
        if not result:
            print("  ✗ papers table not found")
        else:
            old_sql = result[0]
            
            if "excluded" in old_sql:
                print("  ✓ Constraint already includes 'excluded'")
            else:
                print("  Backing up existing papers...")
                # Backup all papers
                cursor.execute("SELECT * FROM papers")
                papers_data = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                print(f"    Found {len(papers_data)} papers to backup")
                
                # Backup FTS data
                cursor.execute("SELECT rowid, title, abstract FROM papers_fts")
                fts_data = cursor.fetchall()
                print(f"    Found {len(fts_data)} FTS entries to backup")
                
                # Create new table with updated constraint
                print("  Creating new papers table with 'excluded' status...")
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
                      status        TEXT NOT NULL CHECK (status IN ('include','maybe','UNSCREENED','excluded')),
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
                print("  Copying data to new table...")
                cursor.execute("""
                    INSERT INTO papers_new 
                    SELECT * FROM papers
                """)
                
                # Drop old table and rename
                print("  Replacing old table...")
                cursor.execute("DROP TABLE papers")
                cursor.execute("ALTER TABLE papers_new RENAME TO papers")
                
                # Recreate indexes
                print("  Recreating indexes...")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(project_id, status)")
                
                # Recreate FTS table
                print("  Recreating FTS table...")
                cursor.execute("DROP TABLE IF EXISTS papers_fts")
                cursor.execute("""
                    CREATE VIRTUAL TABLE papers_fts USING fts5(
                      title, abstract,
                      tokenize='porter'
                    )
                """)
                
                # Restore FTS data
                print("  Restoring FTS data...")
                for rowid, title, abstract in fts_data:
                    cursor.execute(
                        "INSERT INTO papers_fts(rowid, title, abstract) VALUES (?, ?, ?)",
                        (rowid, title, abstract)
                    )
                
                print(f"  ✓ Constraint updated successfully. {len(papers_data)} papers migrated.")
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()

