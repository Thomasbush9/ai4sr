import sqlite3
import sys
from pathlib import Path
from typing import Optional
from . import schema_path
from config import DB_PATH

def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize the database with schema. Safe to call multiple times."""
    path = db_path or DB_PATH
    
    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DB] Initializing database at {path}")
        
        # Read schema
        schema_file = schema_path()
        if not schema_file.exists():
            print(f"[DB ERROR] Schema file not found at {schema_file}", file=sys.stderr)
            raise FileNotFoundError(f"Schema file not found: {schema_file}")
        
        with open(schema_file, "r", encoding="utf-8") as f:
            sql = f.read()
        
        # Execute schema
        with connect(path) as con:
            con.executescript(sql)
            # Verify tables were created
            cursor = con.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"[DB] Database initialized successfully. Tables: {', '.join(tables)}")
            
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize database: {e}", file=sys.stderr)
        raise
