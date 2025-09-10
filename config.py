import os
from pathlib import Path

# go one level up from ai4sr/ → repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("DB_PATH", REPO_ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = str(DB_PATH)
