from pathlib import Path

def schema_path()->Path:
    return Path(__file__).with_name("schema.sql")
