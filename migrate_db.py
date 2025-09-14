#!/usr/bin/env python3
"""
Database migration script to add project_id to conversations table.
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
    """Add project_id column to conversations table and migrate existing data."""
    
    print(f"Migrating database at {DB_PATH}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if project_id column already exists
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'project_id' in columns:
            print("project_id column already exists. Migration not needed.")
            return
        
        print("Adding project_id column to conversations table...")
        
        # Add project_id column
        cursor.execute("ALTER TABLE conversations ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE")
        
        # Get or create default project
        cursor.execute("SELECT id FROM projects WHERE name = 'default'")
        default_project = cursor.fetchone()
        
        if not default_project:
            print("Creating default project...")
            cursor.execute("INSERT INTO projects (name, created_at) VALUES ('default', datetime('now'))")
            default_project_id = cursor.lastrowid
        else:
            default_project_id = default_project['id']
        
        print(f"Default project ID: {default_project_id}")
        
        # Update all existing conversations to use default project
        cursor.execute("UPDATE conversations SET project_id = ? WHERE project_id IS NULL", (default_project_id,))
        updated_rows = cursor.rowcount
        print(f"Updated {updated_rows} conversations to use default project")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
