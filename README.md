# AI4SR - AI-Powered Systematic Review Assistant

An AI-powered literature review assistant that helps researchers find, analyze, and organize academic papers using advanced language models and semantic search.

## Features

- **Literature Review Mode**: Automated paper discovery and screening using AI
- **RAG Chat Mode**: Interactive Q&A about your research papers
- **Project Management**: Organize papers by research projects
- **Smart Screening**: AI-powered relevance scoring and rationale
- **PICO Framework Support**: Structured research question formulation
- **Docker Support**: Easy deployment and distribution

## Prerequisites

- **Python 3.10+** (for local development)
- **Docker & Docker Compose** (for containerized deployment)
- **API Key**: Either:
  - OpenAI API key, OR
  - Azure AI Projects endpoint (see `SETUP_AZURE.md`)

## Quick Start

### Option 1: Docker Deployment (Recommended)

**Step 1: Clone the repository**
```bash
git clone <repository-url>
cd ai4sr
```

**Step 2: Create environment file**
```bash
cp env.example .env
```

**Step 3: Configure API key**
Edit `.env` and add your OpenAI API key:
```bash
OPENAI_KEY=sk-your-api-key-here
```

**Step 4: Generate SSL certificates**
```bash
# Generate self-signed certificates for HTTPS
./nginx/generate-certs.sh
```

**Step 5: Build and run**
```bash
docker-compose up --build -d
```

**Step 6: Verify**
```bash
# Check container status
docker-compose ps

# Check health (HTTPS)
curl -k https://localhost:5001/api/health

# View logs
docker-compose logs -f
```

**Step 7: Access the application**
Open https://localhost:5001 in your browser.

**Note:** Self-signed certificates will trigger a browser security warning. Click "Advanced" → "Proceed to localhost" to continue. For production, replace with certificates from a trusted CA (e.g., Let's Encrypt).

### Option 2: Local Development

**Step 1: Clone and navigate**
```bash
git clone <repository-url>
cd ai4sr
```

**Step 2: Install dependencies**
```bash
pip install -r requirements.txt
pip install -e .
```

**Step 3: Create environment file**
```bash
cp env.example .env
```

**Step 4: Configure API key**
Edit `.env` and add your OpenAI API key:
```bash
OPENAI_KEY=sk-your-api-key-here
```

**Step 5: Run the application**
```bash
python run.py
```

**Step 6: Verify**
```bash
# In another terminal
curl http://localhost:5001/api/health
```

**Step 7: Access the application**
Open http://localhost:5001 in your browser.

**Note:** Local development runs on HTTP. For HTTPS, use Docker deployment with nginx reverse proxy.

## Configuration

### Required Environment Variables

At minimum, you need **one** of the following:

- `OPENAI_KEY`: Your OpenAI API key (get from https://platform.openai.com/api-keys)
- `AZURE_EXISTING_AIPROJECT_ENDPOINT`: Azure AI Project endpoint (see `SETUP_AZURE.md`)

### Production Environment Variables

For production deployments, **required**:
```bash
FLASK_SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
FLASK_ENV=production
```

### Optional Environment Variables

See `env.example` for all available options. Common ones:

```bash
FLASK_PORT=5001              # Port to run on (default: 5001)
FLASK_HOST=0.0.0.0           # Host to bind to (default: 0.0.0.0)
LOG_LEVEL=INFO               # Logging level (DEBUG, INFO, WARNING, ERROR)
DB_PATH=data/review.db       # Database file path
```

## Usage

### Literature Review Mode
1. Click "New Project" to create a research project
2. Ask a research question (e.g., "What are the main causes of overdose in Eastern Europe?")
3. The AI will search PubMed, screen papers, and provide relevant results
4. Papers are scored with detailed rationale for inclusion/exclusion

### RAG Chat Mode
1. Upload your research papers
2. Ask questions about specific papers or research topics
3. Get AI-powered insights from your document collection

### Settings
- Click the ⚙️ Settings button to configure your API key
- Set default paper limits
- Manage project preferences

## Docker Commands

```bash
# Start application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop application
docker-compose down

# Rebuild and restart
docker-compose up --build -d

# Check status
docker-compose ps
```

## Project Structure

```
ai4sr/
├── agents/           # AI agents for literature review and RAG
├── webapp/           # Flask web application
├── db/              # Database schema and connection
├── static/          # Frontend assets (CSS, JS)
├── templates/       # HTML templates
├── data/            # Database and embeddings storage (persisted)
├── logs/            # Application logs (persisted)
├── run.py           # Application entry point
├── Dockerfile       # Container definition
├── docker-compose.yml
└── nginx/           # Nginx reverse proxy configuration
    ├── nginx.conf   # Nginx SSL reverse proxy config
    ├── generate-certs.sh  # Script to generate self-signed certificates
    └── ssl/         # SSL certificates (gitignored)
```

## Troubleshooting

### Docker Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose up --build
```

**Port already in use:**
- Change `FLASK_PORT` in `.env` to a different port (e.g., `5002`)
- Update docker-compose.yml nginx port mapping: `"5002:443"`

**Health check fails:**
- Wait 40 seconds for initial startup
- Check logs: `docker-compose logs -f`
- Verify API key is set in `.env`

### API Key Issues

**"Configuration validation failed":**
- Ensure `OPENAI_KEY` or `AZURE_EXISTING_AIPROJECT_ENDPOINT` is set in `.env`
- Verify the key is valid and has sufficient credits
- Test in Settings panel after starting the app

### Database Issues

**Database errors:**
```bash
# Delete and recreate (data will be lost)
rm data/review.db
# Restart application - database will auto-initialize
```

**Permission errors:**
- Ensure `data/` and `logs/` directories are writable
- In Docker: volumes should be mounted correctly

### Local Development Issues

**Import errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
pip install -e .
```

**Port conflicts:**
- Change `FLASK_PORT` in `.env`
- Or stop existing process: `lsof -ti:5001 | xargs kill`

## Production Deployment

### Requirements
1. Set `FLASK_ENV=production` in `.env`
2. Generate and set `FLASK_SECRET_KEY`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Use a production WSGI server (gunicorn) instead of Flask dev server
4. Configure proper logging and monitoring
5. Replace self-signed SSL certificates with trusted certificates

### HTTPS/SSL Configuration

The application uses nginx as a reverse proxy for HTTPS termination. By default, self-signed certificates are provided for development/testing.

**For Production:**
1. Replace self-signed certificates in `nginx/ssl/` with certificates from a trusted CA:
   - **Let's Encrypt** (free, automated): Use certbot with nginx plugin
   - **Custom certificates**: Place `cert.pem` and `key.pem` in `nginx/ssl/`
2. Update `nginx/nginx.conf` if needed for your certificate setup
3. Restart containers: `docker-compose restart nginx`

**Self-Signed Certificates (Development):**
- Certificates are generated automatically via `./nginx/generate-certs.sh`
- Browsers will show security warnings - this is expected for self-signed certs
- Click "Advanced" → "Proceed to localhost" to bypass the warning

### Docker Production
```bash
# Set production environment
echo "FLASK_ENV=production" >> .env
echo "FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env

# Generate SSL certificates (or use your own)
./nginx/generate-certs.sh

# Deploy
docker-compose up -d
```

## API Endpoints

### Health Check
- `GET /api/health` - Application health status

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create a new project
- `DELETE /api/projects/<id>` - Delete a project

### Conversations
- `POST /api/start` - Start a new conversation
- `GET /api/conversations/<project_id>` - Get conversations for a project
- `GET /api/conversations/<id>/messages` - Get messages for a conversation
- `POST /api/message` - Send a message (literature review or RAG chat)

### PICO
- `POST /api/projects/<id>/pico` - Create/update PICO for a project
- `GET /api/projects/<id>/pico` - Get PICO for a project
- `POST /api/projects/<id>/expand-pico` - Expand PICO into search queries
- `GET /api/projects/<id>/queries` - Get expanded queries

### Corpus Generation
- `POST /api/projects/<id>/generate-corpus` - Generate corpus from queries

## Additional Documentation

- `QUICK_START.md` - Quick testing and verification guide
- `SETUP_AZURE.md` - Azure AI Projects configuration
- `EMBEDDINGS_SETUP.md` - Embeddings configuration details
- `env.example` - All available environment variables

## Development

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -e .

# Run in development mode
FLASK_ENV=development FLASK_DEBUG=True python run.py

# Run tests
python test_app.py
```

## License

This project is licensed under the MIT License.
