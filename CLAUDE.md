# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI4SR is a Flask web application that assists researchers with systematic literature reviews using AI agents, semantic search, and Azure OpenAI/OpenAI integration. It searches PubMed and OpenAlex for papers, screens them with active learning, and provides RAG-based Q&A over collected papers.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run locally (dev mode)
FLASK_ENV=development python run.py

# Run with Docker
docker-compose up --build        # foreground
docker-compose up --build -d     # background

# Stop Docker
docker-compose down

# View Docker logs
docker-compose logs -f

# Initialize database manually
python scripts/init_db.py

# Run tests
python test_app.py               # Flask app & endpoint tests
python test_azure_setup.py       # Azure config validation
python test_embeddings.py        # Embedding model tests
python test_all_agents.py        # Full agent tests
python test_agent_quick.py       # Quick agent smoke tests
python test_db_integration.py    # Database integration tests
python test_screening.py         # Screening logic tests

# Health check
curl http://localhost:5001/api/health           # local
curl -k https://localhost:5001/api/health       # Docker/nginx
```

Makefile shortcuts: `make dev` (development), `make run-docker`, `make stop`, `make logs`, `make install`, `make init-db`.

## Architecture

### Services (Docker)
- **Flask app** on port 5001 (`run.py` → `webapp.create_app()`)
- **Nginx** reverse proxy with HTTPS termination (port 443→5001, port 80 redirects)

### Key Layers

**Web layer** (`webapp/`): Flask app factory in `app.py`, API routes in `routes.py`, Microsoft Entra ID auth in `auth.py`. Single-page frontend served from `templates/index.html` with `static/main.js`.

**Agent layer** (`agents/`): Seven specialized Azure AI agents managed by `azure_config.py`:
- `pico.py` — PICO framework expansion into search queries
- `paper_finder.py` — PubMed/OpenAlex/Crossref paper discovery
- `screener.py` — Active learning screening (TF-IDF + classifier with cold start, uncertainty sampling, stopping rules)
- `rag_agent.py` — Vector DB (FAISS + numpy) for RAG Q&A over papers
- `keyword_exp.py` — DSPy-based keyword/synonym/MeSH concept expansion
- `corpus_generator.py` — Async batch paper fetching
- `orchestrator.py` — Coordinates full literature review pipeline and RAG answers

**Database layer** (`db/`): SQLite at `data/review.db`. Schema in `schema.sql`, connection helper in `connection.py`, data access in `repository.py`. Key tables: `projects`, `papers` (with screening status), `conversations`, `messages`, `pico`, `pico_expansions`, `screening_labels`.

### Critical Patterns

- **Dual API support**: Azure AI Projects primary, OpenAI as fallback. Configured via env vars — at least one of `OPENAI_KEY` or `AZURE_EXISTING_AIPROJECT_ENDPOINT` required. Users can also configure API keys at runtime via the Settings UI, which persists to `settings_store.py` and overrides `.env` values.
- **Message routing**: `POST /api/message` accepts a `modality` field (`"literature"` or `"rag"`) that determines whether the request goes to the literature review pipeline (`orchestrator.literature_review`) or the RAG Q&A pipeline (`orchestrator.rag_answer`).
- **Project isolation**: All data (papers, conversations, vector DBs, PICO) scoped by `project_id`.
- **Paper deduplication**: `_fingerprint()` in `repository.py` hashes normalized title+authors to prevent duplicates across PubMed, OpenAlex, and Crossref.
- **Active learning pipeline**: Cold start (random) → relevance sampling → uncertainty sampling → auto-labeling for high-confidence predictions → stopping rules based on yield rate.
- **Agent caching**: Azure agents are created once and cached; see `get_or_create_agent()` in `azure_config.py`. Call `reset_clients()` to invalidate cache on settings change.
- **Dynamic model discovery**: `GET /api/azure-deployments` queries the Azure Management API to list all deployed models across Cognitive Services accounts. The Settings UI populates chat/embedding model dropdowns from this endpoint.
- **Error handling**: Routes use `@handle_errors` decorator in `routes.py` to standardize HTTP error responses (400 for ValueError/KeyError, 500 for unexpected errors).

### Configuration

Central config in `config.py`. Environment variables loaded from `.env` (see `env.example` for full list). Key vars:
- `AZURE_OPENAI_DEPLOYMENT_NAME` (default: `gpt-4.1`)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` (default: `text-embedding-3-small`)
- `FLASK_SECRET_KEY` (required in production)
- `DB_PATH` (default: `data/review.db`)
- `FLASK_PORT` (default: `5001`)

### Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/start` | Create conversation for a project |
| `POST /api/message` | Send query (literature search or RAG Q&A) |
| `GET /api/projects` | List all projects |
| `POST /api/projects/<id>/pico` | Save PICO framework |
| `POST /api/projects/<id>/expand-pico` | Expand PICO to search queries |
| `POST /api/projects/<id>/generate-corpus` | Batch corpus generation |
| `GET/POST /api/settings` | Read/write runtime API configuration |
| `GET /api/azure-deployments` | List available models from Azure (live query) |
| `GET /api/health` | Health check |
