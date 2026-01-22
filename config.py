"""
Configuration module for AI4SR application.
Validates required environment variables and provides configuration values.
"""
import os
import sys
from pathlib import Path

# Get the project root directory (where config.py is located)
REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", REPO_ROOT / "data" / "review.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = str(DB_PATH)

# Determine if we're in production
IS_PRODUCTION = os.getenv("FLASK_ENV", "").lower() == "production" or os.getenv("ENVIRONMENT", "").lower() == "production"

# Azure AI Projects Configuration
AZURE_EXISTING_AIPROJECT_ENDPOINT = os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
AZURE_OPENAI_DIRECT_ENDPOINT = os.getenv("AZURE_OPENAI_DIRECT_ENDPOINT")  # Optional: direct endpoint for embeddings
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_AGENT_NAME = os.getenv("AZURE_AGENT_NAME", "ai4sr-agent")

# Flask Configuration
# In production, require FLASK_SECRET_KEY to be set
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if IS_PRODUCTION and not FLASK_SECRET_KEY:
    print("ERROR: FLASK_SECRET_KEY must be set in production environment", file=sys.stderr)
    sys.exit(1)
if not FLASK_SECRET_KEY:
    FLASK_SECRET_KEY = "dev-secret-key-change-in-production"
    print("WARNING: Using default development secret key. Set FLASK_SECRET_KEY in production!", file=sys.stderr)

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


def validate_required_config():
    """
    Validate that required configuration is present.
    Called at application startup.
    
    Since the application uses Azure AI Projects, OPENAI_KEY is optional.
    Azure configuration is checked separately when needed.
    """
    errors = []
    
    # Check if either OpenAI key OR Azure configuration is present
    has_openai_key = bool(os.getenv("OPENAI_KEY"))
    has_azure_config = bool(AZURE_EXISTING_AIPROJECT_ENDPOINT)
    
    if not has_openai_key and not has_azure_config:
        errors.append("Either OPENAI_KEY or AZURE_EXISTING_AIPROJECT_ENDPOINT must be set")
    
    # In production, require secret key
    if IS_PRODUCTION and not os.getenv("FLASK_SECRET_KEY"):
        errors.append("FLASK_SECRET_KEY is required in production but not set")
    
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return False
    
    return True
