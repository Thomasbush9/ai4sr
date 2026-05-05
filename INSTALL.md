# AI4SR — Installation & First-Run Guide

This guide takes a brand-new user from zero to a running AI4SR instance with a working literature review and RAG chat. Follow it top-to-bottom; every command is copy-pasteable.

**Estimated time:** 20–30 minutes (excluding Azure resource provisioning, if you also need to do that).

---

## Table of contents

1. [What you are installing](#1-what-you-are-installing)
2. [Prerequisites](#2-prerequisites)
3. [Get the code](#3-get-the-code)
4. [Configure your `.env` file](#4-configure-your-env-file)
5. [TLS certificates](#5-tls-certificates)
6. [Build and start the stack](#6-build-and-start-the-stack)
7. [Verify the install](#7-verify-the-install)
8. [Sign in (Microsoft Entra ID)](#8-sign-in-microsoft-entra-id)
9. [First-time tour: run a literature review](#9-first-time-tour-run-a-literature-review)
10. [Day-2 operations](#10-day-2-operations)
11. [Troubleshooting](#11-troubleshooting)
12. [Quick reference cheat-sheet](#12-quick-reference-cheat-sheet)

---

## 1. What you are installing

AI4SR is a Flask web app that helps researchers run systematic literature reviews. It runs as **two Docker containers**:

| Container | Role | Port |
|---|---|---|
| `ai4sr_app` | Python/Flask app + AI agents + SQLite DB | 5001 (internal only) |
| `ai4sr_nginx` | TLS-terminating reverse proxy | 5001 (HTTPS), 80 (redirect) |

The app calls **Azure OpenAI** (`gpt-4.1` for chat, `text-embedding-3-small` for embeddings) hosted in Azure subscription `EUDA_AzOpenAI_Production`, region `swedencentral`. It also calls **PubMed** and **OpenAlex** (public APIs, no key needed) to discover papers.

User authentication is handled by **Microsoft Entra ID** via the `ai4sr-dev` app registration in tenant `88ffe1c8-07b4-40b5-b4de-00f9b61e942b`.

---

## 2. Prerequisites

Install these on the machine that will host AI4SR **before** you continue:

| Tool | Version | Verify |
|---|---|---|
| **Docker Desktop** (Mac/Windows) or **Docker Engine** (Linux) | 20+ | `docker --version` |
| **Docker Compose** (bundled with Docker Desktop) | v2+ | `docker compose version` or `docker-compose --version` |
| **Git** | any recent | `git --version` |
| **OpenSSL** | for cert generation | `openssl version` |
| **curl** | for health checks | `curl --version` |

You also need:

- **Network access** — outbound HTTPS (port 443) must be allowed to:
  - `*.openai.azure.com` (Azure OpenAI)
  - `*.cognitiveservices.azure.com` (Azure OpenAI direct endpoint)
  - `*.services.ai.azure.com` (Azure AI Foundry projects)
  - `management.azure.com` (model discovery)
  - `login.microsoftonline.com` (Entra ID OAuth)
  - `eutils.ncbi.nlm.nih.gov` (PubMed)
  - `api.openalex.org` (OpenAlex)
- **Free TCP ports** on the host: `5001` (HTTPS) and `80` (redirect)
- An **Azure subscription** with role `Cognitive Services OpenAI User` (or higher) on the AI4SR resource — already configured for the `ai4sr-dev` service principal
- The **MICROSOFT_CLIENT_SECRET** value (ask your Azure admin — it is **not** in the repo)

>  If you don't have Docker yet: install **Docker Desktop** from <https://www.docker.com/products/docker-desktop>, launch it, and wait for the whale icon to stop animating. Then verify with `docker info`.

---

## 3. Get the code

```bash
# Clone the repository
git clone <repository-url> ai4sr
cd ai4sr

# Confirm you're on the production branch
git status
git log -1 --oneline
```

Expected files:

```
docker-compose.yml   ← orchestrates both containers
Dockerfile           ← builds the Flask container
nginx/               ← nginx config + TLS certs go here
env.example          ← template for your config
README.md
INSTALL.md           ← this file
```

---

## 4. Configure your `.env` file

Copy the template and edit it:

```bash
cp env.example .env
```

Open `.env` in your editor. Fill in **at minimum** these values:

```bash
# === Azure OpenAI (REQUIRED) ===
AZURE_EXISTING_AIPROJECT_ENDPOINT=https://oai-ai4sr.services.ai.azure.com/api/projects/oai-ai4sr-project
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small

# === Microsoft Entra ID (REQUIRED for login) ===
MICROSOFT_TENANT_ID=88ffe1c8-07b4-40b5-b4de-00f9b61e942b
MICROSOFT_CLIENT_ID=6e631254-d0bc-4c82-b729-7a9a1c99bee0
MICROSOFT_CLIENT_SECRET=<ask your Azure admin>

# === Flask (REQUIRED in production) ===
FLASK_ENV=production
FLASK_SECRET_KEY=<generate with the command below>
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
```

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output into `FLASK_SECRET_KEY=...`.

**Optional fallback** — if Azure is unreachable, set this and the app will automatically use OpenAI's public API:

```bash
OPENAI_KEY=sk-your-openai-api-key-here
```

> **Security:** the `.env` file contains secrets. It is in `.gitignore` — never commit it. Make sure file permissions are tight: `chmod 600 .env`.

### What each variable does (cheat sheet)

| Variable | Why it matters |
|---|---|
| `AZURE_EXISTING_AIPROJECT_ENDPOINT` | The Azure AI Foundry project URL — primary chat/embedding path |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | The model deployment name (must exist in your Azure resource) |
| `MICROSOFT_CLIENT_SECRET` | Lets the app authenticate as the `ai4sr-dev` service principal |
| `FLASK_SECRET_KEY` | Signs session cookies — anyone who has it can forge sessions |
| `OPENAI_KEY` | Optional fallback so you can demo even if Azure is offline |

---

## 5. TLS certificates

Nginx terminates HTTPS, so you need a certificate at `nginx/ssl/cert.pem` and a key at `nginx/ssl/key.pem`.

### Option A — Self-signed (dev / demo / internal use)

```bash
./nginx/generate-certs.sh
```

This creates a self-signed certificate valid for `localhost` for 365 days. Browsers will show a "Not secure" warning the first time — click **Advanced → Proceed**. This is fine for a demo on your laptop.

### Option B — Trusted CA certificate (production)

If you have a real cert from your organization or Let's Encrypt:

```bash
cp /path/to/your/cert.pem  nginx/ssl/cert.pem
cp /path/to/your/key.pem   nginx/ssl/key.pem
chmod 644 nginx/ssl/cert.pem
chmod 600 nginx/ssl/key.pem
```

The certificate must cover the hostname users will type into their browser (e.g., `ai4sr.euda.europa.eu`). If you use an internal CA, ensure client browsers trust the CA root.

---

## 6. Build and start the stack

```bash
docker-compose up --build -d
```

This:
1. Builds the `ai4sr` image (installs Python deps from `requirements.txt`)
2. Builds the `nginx` image (with HTTPS config baked in)
3. Creates a private Docker network
4. Mounts `./data/` and `./logs/` as persistent volumes
5. Starts both containers in the background

**First build takes 3–5 minutes** (downloads base images and pip packages). Subsequent rebuilds are much faster thanks to layer caching.

Watch the build:

```bash
docker-compose logs -f
```

Press `Ctrl+C` when you see `Running on http://0.0.0.0:5001` — that just exits the log tail; the containers keep running.

---

## 7. Verify the install

Run all of these. Each should succeed.

```bash
# 1. Both containers should show "(healthy)"
docker-compose ps

# 2. Health endpoint via HTTPS
curl -k https://localhost:5001/api/health
# Expect: {"service":"ai4sr","status":"healthy","timestamp":"..."}

# 3. HTTP→HTTPS redirect on port 80
curl -sI http://localhost/api/health | head -1
# Expect: HTTP/1.1 301 Moved Permanently

# 4. Frontend HTML loads
curl -sk https://localhost:5001/ | head -3
# Expect: <!doctype html> ... <title>AI4SR Literature Review</title>

# 5. Live Azure model discovery (proves Azure auth works)
curl -sk https://localhost:5001/api/azure-deployments
# Expect: {"chat_models":[{"deployment":"gpt-4.1",...}], "embedding_models":[...]}

# 6. Real Azure chat completion round-trip
curl -sk -X POST https://localhost:5001/api/test-azure-config -H "Content-Type: application/json" -d '{}'
# Expect: {"message":"Azure OpenAI configuration is valid","success":true}
```

If all six pass, the install is complete. Open <https://localhost:5001> in your browser.

> **Tip:** if a healthcheck initially says `(starting)`, wait 40 seconds — that's the configured `start_period`. After ~60 seconds it should flip to `(healthy)`. If it flips to `(unhealthy)` instead, jump to [Troubleshooting](#11-troubleshooting).

---

## 8. Sign in (Microsoft Entra ID)

1. Open <https://localhost:5001> and accept the self-signed cert warning.
2. Click **Login with Microsoft** (top-right).
3. You'll be redirected to `login.microsoftonline.com`. Sign in with your **EUDA work account** (must be in tenant `88ffe1c8-07b4-40b5-b4de-00f9b61e942b`).
4. On first login you may be asked to consent to `User.Read` — accept.
5. You'll be redirected back to AI4SR with your name in the top-right.

> **Warning:** the redirect URI must be registered in Azure Portal. For `localhost`, the URI `https://localhost:5001/auth/callback` must already be added under **App registrations → ai4sr-dev → Authentication**. If you see error `AADSTS50011`, ask your Azure admin to add it.

---

## 9. First-time tour: run a literature review

Now let's verify the AI pipeline end-to-end.

### Step 1 — Confirm the model is wired up

1. Click the gear icon (top-right) → **Settings**.
2. Click **Refresh models from Azure**.
3. The **Chat Model** dropdown should populate with `gpt-4.1`. Embedding dropdown should show `text-embedding-3-small` and `text-embedding-3-large`.
4. Click **Test Azure Configuration** → expect a green "valid" message.
5. Close Settings.

### Step 2 — Create a project

1. Top-right → **New Project**.
2. Name it `demo-test` (alphanumeric, hyphens, underscores, dots only — max 128 chars).
3. Select it as the active project.

### Step 3 — Run a literature review

1. Switch the mode tabs to **PICO Review** or stay on **RAG Chat**.
2. For a fast check: switch to literature mode and paste:
   > *"What are the effects of SGLT2 inhibitors on heart failure outcomes?"*
3. Set N (number of papers) to `10` for speed.
4. Submit.

What happens behind the scenes (you'll see this in `docker-compose logs -f`):
- Keyword agent expands the question
- Concept agent generates synonyms + Boolean PubMed query
- PubMed + OpenAlex fetched in parallel, deduped
- Two-stage screener (basic relevance → CoT PICO scoring)
- Results stored in SQLite, scored papers shown in UI

First run may take 20–60 seconds (cold start). Subsequent calls are faster (agent cache warm).

### Step 4 — Try RAG mode

1. Switch to **RAG Chat** mode.
2. Ask: *"What is the consensus on SGLT2 inhibitor effects on hospitalization?"*
3. The app embeds your question, finds the most similar papers in the corpus, and synthesizes an answer with citations.

If both flows return results, **the install is fully working**.

---

## 10. Day-2 operations

### Stop, start, restart

```bash
docker-compose stop          # graceful stop, keep containers
docker-compose start         # start them again
docker-compose restart       # restart in place (after .env change)
docker-compose down          # stop + remove containers (data preserved)
docker-compose up --build -d # rebuild and start (after code change)
```

### View logs

```bash
docker-compose logs -f             # follow both services
docker-compose logs -f ai4sr       # Flask app only
docker-compose logs -f nginx       # nginx only
docker-compose logs --tail=200 ai4sr   # last 200 lines
```

Logs also persist on disk at `./logs/app.log`.

### Backup the database

```bash
docker-compose down
cp -r data/ backup/data-$(date +%Y%m%d)/
docker-compose up -d
```

The DB is SQLite WAL mode — it can be copied while running, but stopping first guarantees consistency.

### Restore from backup

```bash
docker-compose down
rm -rf data/
cp -r backup/data-YYYYMMDD/ data/
docker-compose up -d
```

### Update to a newer version

```bash
git pull
docker-compose up --build -d
curl -k https://localhost:5001/api/health
```

The DB schema auto-migrates on startup.

### Change a config value

Edit `.env`, then:

```bash
docker-compose restart
```

(A full `up --build` is only needed if you change `Dockerfile` or `requirements.txt`.)

### Wipe everything and start fresh

```bash
docker-compose down
rm -rf data/ logs/   #  deletes all projects, papers, conversations, embeddings
docker-compose up --build -d
```

---

## 11. Troubleshooting

### Containers won't start

```bash
docker-compose logs ai4sr | tail -50
docker-compose logs nginx | tail -50
```

Most common causes:
- `.env` missing or has syntax errors (no quotes around values, no spaces around `=`)
- `FLASK_SECRET_KEY` not set in production mode
- `MICROSOFT_CLIENT_SECRET` not set
- TLS cert files missing at `nginx/ssl/cert.pem` and `nginx/ssl/key.pem`

### Healthcheck shows `(unhealthy)`

```bash
docker inspect -f '{{json .State.Health}}' ai4sr_app | python -m json.tool
```

Look at the last few `Log` entries for the error. Restart with verbose logging:

```bash
# Add LOG_LEVEL=DEBUG to .env
docker-compose restart
docker-compose logs -f ai4sr
```

### "Port 5001 already in use"

```bash
# macOS / Linux: find the process using port 5001
lsof -ti:5001
# Kill it
lsof -ti:5001 | xargs kill -9
# Or change the port in .env (FLASK_PORT=5002) and in docker-compose.yml ("5002:443")
```

### `AADSTS50011: redirect URI does not match`

The URI the app sent doesn't match what's registered in Azure Portal.

**Fix:**
- Leave `MICROSOFT_REDIRECT_URI` **unset** in `.env` — the app auto-detects from the request URL.
- Verify the URI in Azure Portal: **App registrations → ai4sr-dev → Authentication → Redirect URIs**. Must include exactly `https://localhost:5001/auth/callback` (for local dev) or your production URL.
- If running behind a load balancer that rewrites the host header, set `MICROSOFT_REDIRECT_URI` explicitly to the **external** URL users see.

### `AADSTS700016: Application not found in tenant`

`MICROSOFT_CLIENT_ID` or `MICROSOFT_TENANT_ID` is wrong. Verify against Azure Portal **App registrations → ai4sr-dev → Overview**.

### "Login with Microsoft" button does nothing

`MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, or `MICROSOFT_TENANT_ID` not set. Check `.env` and restart.

### `Azure chat completion failed and OPENAI_KEY not set for fallback`

Neither Azure nor OpenAI is reachable. Check in order:

1. `AZURE_EXISTING_AIPROJECT_ENDPOINT` is set in `.env`
2. Service principal credentials are correct (`MICROSOFT_CLIENT_ID/SECRET/TENANT_ID`)
3. The service principal has `Cognitive Services OpenAI User` role on the `oai-ai4sr` resource (Azure Portal → `oai-ai4sr` → Access control (IAM))
4. Network allows outbound HTTPS to `*.openai.azure.com` and `*.services.ai.azure.com`
5. As a quick fallback for the demo: set `OPENAI_KEY=sk-...` in `.env` and `docker-compose restart`

### "Database is locked"

SQLite uses WAL mode + 30s busy timeout, so this usually self-recovers. If persistent:

```bash
docker-compose restart
```

If a backup file is still open from a crashed process:

```bash
docker-compose down
ls data/review.db*    # check for stray .db-journal or .db-wal
docker-compose up -d  # WAL is replayed on startup
```

### Browser shows "Your connection is not private"

Self-signed cert — expected. Click **Advanced → Proceed to localhost (unsafe)**. For production, use Option B in [Section 5](#5-tls-certificates).

### Settings page shows masked secrets like `3Qz8****lc~P`

That's intentional — secrets are masked when read back via `/api/settings` so they aren't leaked into browser history or screenshots.

### A literature review query just hangs

- Check `docker-compose logs -f ai4sr` for traceback.
- PubMed sometimes rate-limits — retry after 30 seconds.
- The first call is slow because Azure agents are cold. Pre-warm by running one tiny query (N=5) before the demo.

### "Refresh models from Azure" returns no models

The service principal lacks `Reader` access at the subscription or resource group level. Add **Reader** role at **subscription scope** for the SP — see `AZURE_PERMISSIONS.md`.

---

## 12. Quick reference cheat-sheet

```bash
# Start
docker-compose up --build -d

# Stop
docker-compose down

# Restart (after .env change)
docker-compose restart

# Logs
docker-compose logs -f

# Health
curl -k https://localhost:5001/api/health

# Status
docker-compose ps

# Open the UI
open https://localhost:5001        # macOS
xdg-open https://localhost:5001    # Linux
start https://localhost:5001       # Windows
```

| Endpoint | Use |
|---|---|
| `/api/health` | Liveness probe |
| `/api/azure-deployments` | Live model list from Azure |
| `/api/test-azure-config` | Smoke-test Azure chat completion |
| `/api/settings` | Read/write runtime config |
| `/api/projects` | List projects |

---

## Done

If you got this far and step 7 passed, you have a working AI4SR install. For deeper architecture, model selection, or PICO workflow details, see `README.md`.

**For the demo:** keep `docker-compose logs -f ai4sr` open in a second terminal — when something breaks, the answer is almost always there.
