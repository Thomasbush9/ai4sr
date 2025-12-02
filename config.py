import os
from pathlib import Path

# Get the project root directory (where config.py is located)
REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", REPO_ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = str(DB_PATH)

# OpenAlex API configuration
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "thomasbush52@gmail.com")
MAX_CITATIONS_BACKWARD = int(os.getenv("MAX_CITATIONS_BACKWARD", "10"))
MAX_CITATIONS_FORWARD = int(os.getenv("MAX_CITATIONS_FORWARD", "10"))
MAX_SIMILAR_PAPERS = int(os.getenv("MAX_SIMILAR_PAPERS", "10"))
OPENALEX_REQUEST_DELAY = 0.1  # polite delay between OpenAlex calls (seconds)

# Semantic Scholar API configuration
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", None)  # Optional, free tier available
SEMANTIC_SCHOLAR_REQUEST_DELAY = 0.1  # polite delay between Semantic Scholar calls (seconds)
