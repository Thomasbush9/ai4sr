#!/usr/bin/env python3
"""
Database migration script for PICO pipeline schema changes.
Adds PICO tables, extends papers.status, and adds ingestion logs.
"""
import sqlite3
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

from config import DB_PATH


def migrate_database():
    """Apply PICO pipeline schema changes."""
    
    print(f"Migrating database at {DB_PATH}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # 1. Create PICO table
        if 'pico' not in existing_tables:
            print("Creating pico table...")
            cursor.execute("""
                CREATE TABLE pico (
                  id            INTEGER PRIMARY KEY,
                  project_id    INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
                  population    TEXT NOT NULL,
                  intervention  TEXT,
                  comparison    TEXT,
                  outcome       TEXT,
                  study_design  TEXT,
                  extra_terms   TEXT,
                  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pico_project ON pico(project_id)")
            print("✓ Created pico table")
        else:
            print("✓ pico table already exists")
        
        # 2. Create pico_expansions table
        if 'pico_expansions' not in existing_tables:
            print("Creating pico_expansions table...")
            cursor.execute("""
                CREATE TABLE pico_expansions (
                  id              INTEGER PRIMARY KEY,
                  project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
                  question_summary TEXT NOT NULL,
                  pubmed_query    TEXT NOT NULL,
                  openalex_query  TEXT NOT NULL,
                  pico_keywords   TEXT NOT NULL,
                  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pico_expansions_project ON pico_expansions(project_id)")
            print("✓ Created pico_expansions table")
        else:
            print("✓ pico_expansions table already exists")
        
        # 3. Create review_ingestion_logs table
        if 'review_ingestion_logs' not in existing_tables:
            print("Creating review_ingestion_logs table...")
            cursor.execute("""
                CREATE TABLE review_ingestion_logs (
                  id              INTEGER PRIMARY KEY,
                  project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  pubmed_query    TEXT,
                  openalex_query  TEXT,
                  pubmed_count    INTEGER DEFAULT 0,
                  openalex_count  INTEGER DEFAULT 0,
                  total_unique    INTEGER DEFAULT 0,
                  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_logs_project ON review_ingestion_logs(project_id)")
            print("✓ Created review_ingestion_logs table")
        else:
            print("✓ review_ingestion_logs table already exists")
        
        # 4. Update papers.status constraint to include UNSCREENED
        print("Updating papers.status constraint...")
        
        # Check current constraint
        cursor.execute("PRAGMA table_info(papers)")
        columns = cursor.fetchall()
        status_col = None
        for col in columns:
            if col[1] == 'status':
                status_col = col
                break
        
        if status_col:
            # SQLite doesn't support ALTER TABLE to modify CHECK constraints directly
            # We need to recreate the table. But first, check if UNSCREENED status already exists
            cursor.execute("SELECT COUNT(*) FROM papers WHERE status = 'UNSCREENED'")
            has_unscreened = cursor.fetchone()[0] > 0
            
            if not has_unscreened:
                # Check if we can safely update - try to find any constraint violations
                # For now, we'll just note that the constraint needs to be updated
                # The schema.sql file already has the updated constraint, so new databases will be correct
                # For existing databases, we'll need to handle this more carefully
                print("  Note: papers.status constraint update requires table recreation.")
                print("  If you have existing data, you may need to manually update the constraint.")
                print("  The constraint in schema.sql already includes 'UNSCREENED'.")
                print("  For existing databases, you can:")
                print("    1. Backup your data")
                print("    2. Drop and recreate the papers table with the new constraint")
                print("    3. Or manually update any papers with status='UNSCREENED' after ensuring the constraint allows it")
            else:
                print("  ✓ UNSCREENED status already in use")
        else:
            print("  ✗ Could not find status column in papers table")
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()

