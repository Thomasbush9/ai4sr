# AI4SR - AI-Powered Systematic Review Assistant

An AI-powered literature review assistant that helps researchers find, analyze, and organize academic papers using Azure OpenAI (or OpenAI as fallback) and semantic search.

## Features

- **Literature Review Mode**: Automated paper discovery from PubMed + OpenAlex with AI screening
- **RAG Chat Mode**: Interactive Q&A over your collected papers
- **Project Management**: Isolate papers, conversations, and embeddings per project
- **Smart Screening**: Two-stage AI screening (basic relevance → detailed PICO analysis)
- **PICO Framework**: Structured research question → search query expansion
- **Active Learning**: Cold-start labeling, uncertainty sampling, and auto-labeling

---

## Deployment Guide (IT / Infrastructure)

### Prerequisites

| Requirement | Details |
|---|---|
| Docker & Docker Compose | v20+ recommended |
| Azure OpenAI resource | With a chat deployment (e.g. `gpt-4.1`) |
| Azure Embedding deployment | `text-embedding-3-small` (or equivalent) |
| TLS certificate | Self-signed for dev; trusted CA cert for production |

### Network / Firewall Requirements

| Port | Direction | Protocol | Purpose |
|---|---|---|---|
| **5001** (or your chosen port) | Inbound | HTTPS | User access (nginx → Flask) |
| **80** | Inbound | HTTP | Redirects to HTTPS |
| **443** | Outbound | HTTPS | Azure OpenAI API (`*.openai.azure.com`) |
| **443** | Outbound | HTTPS | Azure Management API (`management.azure.com`) |
| **443** | Outbound | HTTPS | Microsoft Entra ID (`login.microsoftonline.com`) |
| **443** | Outbound | HTTPS | PubMed API (`eutils.ncbi.nlm.nih.gov`) |
| **443** | Outbound | HTTPS | OpenAlex API (`api.openalex.org`) |

### 1. Clone and configure

```bash
git clone <repository-url>
cd ai4sr
cp env.example .env
```

Edit `.env` with your values. **Minimum required for Azure:**

```bash
# Azure OpenAI
AZURE_OPENAI_DIRECT_ENDPOINT=https://oai-ai4sr.cognitiveservices.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small

# Azure authentication (service principal)
MICROSOFT_TENANT_ID=88ffe1c8-07b4-40b5-b4de-00f9b61e942b
MICROSOFT_CLIENT_ID=6e631254-d0bc-4c82-b729-7a9a1c99bee0
MICROSOFT_CLIENT_SECRET=<your-client-secret>

# Flask (REQUIRED in production)
FLASK_ENV=production
FLASK_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

> **Fallback**: If Azure is unavailable, set `OPENAI_KEY=sk-...` instead. The app will use OpenAI's API for both chat and embeddings.

### 2. TLS certificates

The nginx reverse proxy terminates TLS. You have two options:

**Option A — Self-signed (dev/testing only):**
```bash
./nginx/generate-certs.sh
```

**Option B — Trusted CA certificate (production):**
```bash
# Place your certificate and private key at:
cp /path/to/your/cert.pem  nginx/ssl/cert.pem
cp /path/to/your/key.pem   nginx/ssl/key.pem
```

The certificate must cover the hostname users will access (e.g., `ai4sr.euda.europa.eu`).

If using an internal CA, ensure client browsers/machines trust the CA root certificate (via GPO, MDM, or manual install).

### 3. Build and start

```bash
docker-compose up --build -d
```

Verify:
```bash
docker-compose ps                                  # both services should be "Up"
curl -k https://localhost:5001/api/health           # {"status":"healthy",...}
docker-compose logs -f                              # watch logs
```

### 4. Microsoft Entra ID login (optional)

An app registration (`ai4sr-dev`) already exists in tenant `88ffe1c8-07b4-40b5-b4de-00f9b61e942b`. To enable user login:

1. Add these to `.env`:
   ```bash
   MICROSOFT_CLIENT_ID=6e631254-d0bc-4c82-b729-7a9a1c99bee0
   MICROSOFT_CLIENT_SECRET=<your-client-secret>
   MICROSOFT_TENANT_ID=88ffe1c8-07b4-40b5-b4de-00f9b61e942b
   ```
2. Ensure the **Redirect URI** in Azure Portal matches your deployment URL:
   - Azure Portal → App registrations → `ai4sr-dev` → Authentication → Web → Redirect URIs
   - Production: `https://ai4sr.euda.europa.eu:5001/auth/callback` (already registered)
   - Local dev: add `https://localhost:5001/auth/callback` (ask an admin)
3. Leave `MICROSOFT_REDIRECT_URI` **unset** in `.env` — the app auto-detects it from the request URL
4. Restart: `docker-compose restart`

> **Important**: The redirect URI must exactly match one of the URIs registered in Azure Portal. If they don't match, Entra ID will reject the callback with `AADSTS50011`. If running behind a reverse proxy that changes the Host header, set `MICROSOFT_REDIRECT_URI` explicitly in `.env` to the external URL users see.

**Current app registration:**
| Setting | Value |
|---|---|
| App name | `ai4sr-dev` |
| App (client) ID | `6e631254-d0bc-4c82-b729-7a9a1c99bee0` |
| Tenant | `88ffe1c8-07b4-40b5-b4de-00f9b61e942b` (AzureADMyOrg) |
| Redirect URI | `https://ai4sr.euda.europa.eu:5001/auth/callback` |
| API permission | `User.Read` (delegated, Microsoft Graph) |
| Auth flow | Authorization Code (MSAL ConfidentialClient) |

### 5. Azure service principal permissions

The `ai4sr-dev` service principal already has the following roles on `oai-ai4sr`:

| Role | Scope | Purpose |
|---|---|---|
| **Cognitive Services OpenAI User** | `oai-ai4sr` | Chat completions + embeddings |
| **Azure AI User** | `oai-ai4sr` | AI service access |
| **Azure AI Developer** | `oai-ai4sr` | Agent/project operations |

Two users also have **Azure AI User** + **Cognitive Services OpenAI Contributor** on the `oai-ai4sr-project`.

To add a new user or service principal: Azure Portal → `oai-ai4sr` → Access control (IAM) → Add role assignment → assign **Cognitive Services OpenAI User** at minimum.

### 6. Data persistence and backup

Docker volumes mount local directories into the containers:

| Container path | Host path | Contains |
|---|---|---|
| `/app/data` | `./data/` | SQLite database (`review.db`), runtime settings, RAG embeddings |
| `/app/logs` | `./logs/` | Application logs |

**Backup:**
```bash
# Stop the app (ensures clean DB state)
docker-compose down

# Copy the data directory
cp -r data/ backup/data-$(date +%Y%m%d)/

# Restart
docker-compose up -d
```

**Restore:**
```bash
docker-compose down
cp -r backup/data-YYYYMMDD/ data/
docker-compose up -d
```

The SQLite database uses WAL mode — it can be safely copied while the app is running, but stopping first guarantees consistency.

### 7. Updating / upgrading

```bash
# Pull latest code
git pull origin main

# Rebuild and restart (data is preserved in volumes)
docker-compose up --build -d

# Verify
curl -k https://localhost:5001/api/health
```

The database schema auto-migrates on startup (`init_db()` in `run.py`).

### 8. Monitoring

- **Health check**: `GET /api/health` — returns `{"status": "healthy"}` or 503
- **Docker healthcheck**: Both containers have built-in healthchecks (every 30s, 3 retries)
- **Logs**: `docker-compose logs -f` or check `./logs/app.log` on the host
- **Log level**: Set `LOG_LEVEL=DEBUG` in `.env` for verbose output

---

## Configuration Reference

### Required (production)

| Variable | Description |
|---|---|
| `FLASK_SECRET_KEY` | Random 64-char hex string for session signing |
| `FLASK_ENV` | Set to `production` |

### Azure OpenAI

| Variable | Default | Description |
|---|---|---|
| `AZURE_OPENAI_DIRECT_ENDPOINT` | (derived) | Direct Azure OpenAI endpoint, e.g. `https://oai-ai4sr.cognitiveservices.azure.com` |
| `AZURE_EXISTING_AIPROJECT_ENDPOINT` | — | AI Projects endpoint (alternative to direct endpoint) |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4.1` | Chat completion deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | `text-embedding-3-small` | Embedding deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | Azure OpenAI API version |

### Authentication

| Variable | Description |
|---|---|
| `MICROSOFT_TENANT_ID` | Azure AD tenant ID |
| `MICROSOFT_CLIENT_ID` | App registration client ID |
| `MICROSOFT_CLIENT_SECRET` | App registration client secret |
| `MICROSOFT_REDIRECT_URI` | OAuth callback URL (auto-detected if not set) |

### Fallback

| Variable | Description |
|---|---|
| `OPENAI_KEY` | OpenAI API key — used when Azure is unavailable |

### Optional

| Variable | Default | Description |
|---|---|---|
| `FLASK_PORT` | `5001` | Application port |
| `FLASK_HOST` | `0.0.0.0` | Bind address |
| `DB_PATH` | `data/review.db` | SQLite database path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `OPENALEX_EMAIL` | `noreply@example.com` | Polite pool email for OpenAlex API |

All variables can also be configured at runtime via the Settings UI (gear icon in the app). Runtime settings are stored in `data/runtime_settings.json` with `0600` permissions and override `.env` values.

---

## Security Notes

- **Session cookies** are `HttpOnly`, `SameSite=Lax`, and `Secure` (in production)
- **CSRF protection**: state-changing requests are checked against the `Origin` header
- **API keys** stored in `data/runtime_settings.json` are file-permission-protected (`0600`). For higher security, use Azure Key Vault and inject secrets as environment variables
- **Error messages** returned to clients are generic; details are logged server-side only
- **Project names** are validated (alphanumeric, spaces, hyphens, underscores, dots; max 128 chars)
- **No zip/archive files** should be committed to the repository
- **Client secret rotation**: when rotating the `MICROSOFT_CLIENT_SECRET`, update `.env` and run `docker-compose restart`

---

## Troubleshooting

### Authentication / Login Issues

**`AADSTS50011: The redirect URI does not match`**
- The redirect URI sent by the app doesn't match what's registered in Azure Portal
- Fix: leave `MICROSOFT_REDIRECT_URI` unset in `.env` (auto-detect), or set it to exactly match the registered URI
- Check registered URIs: Azure Portal → App registrations → `ai4sr-dev` → Authentication

**`AADSTS700016: Application not found in tenant`**
- The `MICROSOFT_CLIENT_ID` or `MICROSOFT_TENANT_ID` is wrong
- Verify values match the app registration in Azure Portal

**Login button does nothing / "Failed to initiate login"**
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, or `MICROSOFT_TENANT_ID` not set
- Check `.env` or configure via Settings UI

### Azure OpenAI Issues

**`Azure chat completion failed and OPENAI_KEY not set for fallback`**
- Neither Azure nor OpenAI is reachable. Check:
  1. `AZURE_OPENAI_DIRECT_ENDPOINT` or `AZURE_EXISTING_AIPROJECT_ENDPOINT` is set
  2. Service principal credentials are correct
  3. Network allows outbound HTTPS to `*.openai.azure.com`

**`Azure configuration test failed`**
- Click "Test Azure Configuration" in Settings — check server logs (`docker-compose logs -f`) for details
- Common cause: deployment name doesn't exist on the endpoint (use "Refresh models from Azure" in Settings to see available models)

### Docker Issues

**Container won't start / keeps restarting:**
```bash
docker-compose logs ai4sr        # check Flask app logs
docker-compose logs nginx         # check nginx logs
```

**Port 5001 already in use:**
```bash
lsof -ti:5001 | xargs kill       # kill existing process
# Or change port in .env: FLASK_PORT=5002
# And update docker-compose.yml: "5002:443" under nginx ports
```

**Health check fails after startup:**
- Wait 40 seconds (start_period is 40s)
- Check if `.env` has valid API credentials
- Check `docker-compose logs -f` for errors

### Database Issues

**"Database locked" errors:**
- SQLite uses WAL mode with 30s timeout — this handles most concurrency
- If persistent: restart the app (`docker-compose restart`)

**Corrupt database / fresh start:**
```bash
docker-compose down
rm data/review.db                 # WARNING: deletes all data
docker-compose up -d              # database auto-recreates
```

---

## Usage

### Literature Review Mode
1. Create a project (click "New Project")
2. Type a research question (e.g., "What are the effects of SGLT2 inhibitors on heart failure?")
3. The app searches PubMed + OpenAlex, screens papers with AI, and stores results
4. Review papers with relevance scores and PICO-based rationale

### RAG Chat Mode
1. Switch to RAG mode on an existing project
2. Ask questions about your collected papers
3. The AI retrieves relevant papers via embeddings and synthesizes an answer

### Model Selection
Users can choose which Azure OpenAI model to use via **Settings > Chat Model**:
- The dropdown is populated live from your Azure subscription (click "Refresh models from Azure")
- Shows all deployed chat and embedding models across your Cognitive Services accounts
- You can also type a custom deployment name manually
- Changes take effect immediately for all subsequent requests

### PICO Framework
1. Define Population, Intervention, Comparison, Outcome for your project
2. Click "Expand PICO" to generate optimized search queries
3. Use "Generate Corpus" to run the expanded queries at scale

---

## Docker Commands

```bash
docker-compose up --build -d        # Build and start
docker-compose down                 # Stop
docker-compose logs -f              # Stream logs
docker-compose restart              # Restart after config change
docker-compose ps                   # Check status
```

## Local Development

```bash
# Using conda (recommended)
conda activate ai4sr
pip install -r requirements.txt
pip install -e .

# Run in dev mode
FLASK_ENV=development python run.py

# Run tests
python test_app.py                  # App + endpoint tests
python test_azure_setup.py          # Azure config validation
python test_embeddings.py           # Embedding tests
```

Makefile shortcuts: `make dev`, `make run-docker`, `make stop`, `make logs`.

---

## Architecture

```
webapp/          Flask app (routes.py, auth.py)
agents/          AI agents — all use azure_config.chat_completion()
  azure_config.py   AzureOpenAI client, chat + embedding with OpenAI fallback
  orchestrator.py   Coordinates literature review pipeline + RAG Q&A
  screening.py      Two-stage screener (basic + CoT PICO analysis)
  keyword_exp.py    Query expansion (keywords → concepts → Boolean queries)
  pico.py           PICO framework → search query generation
  rag_agent.py      Vector DB (numpy) + similarity search + LLM answer
  review_agent.py   Structured paper summary extraction
  cold_start_agent.py  Seeds active learning with initial labels
db/              SQLite (schema.sql, repository.py)
static/          SPA frontend (main.js, style.css)
templates/       index.html
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/start` | Create conversation |
| POST | `/api/message` | Send query (modality: `literature` or `rag`) |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| DELETE | `/api/projects/<id>` | Delete project |
| POST | `/api/projects/<id>/pico` | Save PICO |
| POST | `/api/projects/<id>/expand-pico` | Expand PICO to queries |
| POST | `/api/projects/<id>/generate-corpus` | Batch corpus generation |
| GET/POST | `/api/settings` | Read/write runtime config |
| GET | `/api/azure-deployments` | List available models from Azure |
| POST | `/api/test-azure-config` | Validate Azure connection |

## Additional Documentation

- `SETUP_AZURE.md` — Azure AI Projects setup
- `EMBEDDINGS_SETUP.md` — Embedding deployment configuration
- `CREDENTIALS_GUIDE.md` — Service principal setup
- `env.example` — All environment variables with descriptions

## License

This project is licensed under the MIT License.
