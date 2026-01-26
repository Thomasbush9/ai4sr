#!/usr/bin/env python3
"""
Database migration script for agent review tables.
Adds agent_summaries and project_agent_overview tables.
"""
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import DB_PATH


def migrate_database():
    """Apply agent review schema changes."""
    print(f"Migrating database at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # 1. Create agent_summaries table
        if 'agent_summaries' not in existing_tables:
            print("Creating agent_summaries table...")
            cursor.execute("""
                CREATE TABLE agent_summaries (
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_summaries_project ON agent_summaries(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_summaries_paper ON agent_summaries(paper_id)")
            print("✓ Created agent_summaries table")
        else:
            print("✓ agent_summaries table already exists")
        
        # 2. Create project_agent_overview table
        if 'project_agent_overview' not in existing_tables:
            print("Creating project_agent_overview table...")
            cursor.execute("""
                CREATE TABLE project_agent_overview (
                  id              INTEGER PRIMARY KEY,
                  project_id      INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
                  overview_json   TEXT NOT NULL,
                  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_agent_overview_project ON project_agent_overview(project_id)")
            print("✓ Created project_agent_overview table")
        else:
            print("✓ project_agent_overview table already exists")
        
        conn.commit()
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()

