import os
from pathlib import Path

# Get the project root directory (where config.py is located)
REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", REPO_ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = str(DB_PATH)

# Azure AI Projects Configuration
AZURE_EXISTING_AIPROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
AZURE_AGENT_NAME = os.getenv("AZURE_AGENT_NAME", "ai4sr-agent")

# Flask Configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Microsoft Authentication Configuration
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5000/auth/callback")

# OpenAlex API configuration
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "noreply@example.com")
MAX_CITATIONS_BACKWARD = int(os.getenv("MAX_CITATIONS_BACKWARD", "10"))
MAX_CITATIONS_FORWARD = int(os.getenv("MAX_CITATIONS_FORWARD", "10"))
MAX_SIMILAR_PAPERS = int(os.getenv("MAX_SIMILAR_PAPERS", "10"))
OPENALEX_REQUEST_DELAY = 0.1  # polite delay between OpenAlex calls (seconds)

# Semantic Scholar API configuration
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", None)  # Optional, free tier available
SEMANTIC_SCHOLAR_REQUEST_DELAY = 0.1  # polite delay between Semantic Scholar calls (seconds)

# Corpus generation limits (server-side, not user-configurable)
MAX_PUBMED_RESULTS_PER_REVIEW = int(os.getenv("MAX_PUBMED_RESULTS_PER_REVIEW", "2000"))
MAX_OPENALEX_RESULTS_PER_REVIEW = int(os.getenv("MAX_OPENALEX_RESULTS_PER_REVIEW", "2000"))
