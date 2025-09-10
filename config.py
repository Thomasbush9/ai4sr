import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
