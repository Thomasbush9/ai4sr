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
python test_app.py
python test_azure_setup.py       # Azure config validation
python test_embeddings.py        # Embedding model tests
python test_all_agents.py        # Full agent tests
python test_agent_quick.py       # Quick agent smoke tests

# Health check
curl http://localhost:5001/api/health           # local
curl -k https://localhost:5001/api/health       # Docker/nginx
```

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

- **Dual API support**: Azure AI Projects primary, OpenAI as fallback. Configured via env vars — at least one of `OPENAI_KEY` or `AZURE_EXISTING_AIPROJECT_ENDPOINT` required.
- **Project isolation**: All data (papers, conversations, vector DBs, PICO) scoped by `project_id`.
- **Paper deduplication**: `_fingerprint()` in `repository.py` hashes normalized title+authors to prevent duplicates.
- **Active learning pipeline**: Cold start (random) → relevance sampling → uncertainty sampling → auto-labeling for high-confidence predictions → stopping rules based on yield rate.
- **Agent caching**: Azure agents are created once and cached; see `get_or_create_agent()` in `azure_config.py`.

### Configuration

Central config in `config.py`. Environment variables loaded from `.env` (see `env.example` for full list). Key vars:
- `AZURE_OPENAI_DEPLOYMENT_NAME` (default: `gpt-4o-mini`)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` (default: `text-embedding-3-small`)
- `FLASK_SECRET_KEY` (required in production)
- `DB_PATH` (default: `data/review.db`)
- `FLASK_PORT` (default: `5001`)
