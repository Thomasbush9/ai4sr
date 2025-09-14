import sqlite3
from pathlib import Path
from . import schema_path
from config import DB_PATH

def connect(db_path:Path | None=None)-> sqlite3.Connection:
    path = db_path or DB_PATH
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db(db_path:Path | None = None) -> None:
    path = db_path or DB_PATH
    with open(schema_path(), "r", encoding="utf-8") as f:
        sql = f.read()
    with connect(path) as con:
        con.executescript(sql)
