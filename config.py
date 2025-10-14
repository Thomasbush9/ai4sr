import os
from pathlib import Path

# Get the project root directory (where config.py is located)
REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", REPO_ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = str(DB_PATH)
