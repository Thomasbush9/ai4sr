# AI4SR - Literature Review Assistant

An AI-powered literature review assistant that helps researchers find, analyze, and organize academic papers using advanced language models and semantic search.

## Features

- **Literature Review Mode**: Automated paper discovery and screening using AI
- **RAG Chat Mode**: Interactive Q&A about your research papers
- **Project Management**: Organize papers by research projects
- **Smart Screening**: AI-powered relevance scoring and rationale
- **PICO Framework Support**: Structured research question formulation
- **Docker Support**: Easy deployment and distribution
- **Health Monitoring**: Built-in health check endpoints

## Architecture

```
┌─────────────┐
│   Frontend  │ (HTML/CSS/JS)
└──────┬──────┘
       │ HTTP/REST
┌──────▼──────┐
│  Flask App  │ (webapp/)
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌──▼────┐
│ DB  │ │Agents │
└─────┘ └───────┘
```

**Components:**
- **Web Application** (`webapp/`): Flask-based REST API and web interface
- **AI Agents** (`agents/`): Specialized agents for literature review, RAG, PICO expansion
- **Database** (`db/`): SQLite database with schema management
- **Utilities** (`utils/`): Logging, configuration, and shared utilities

## Quick Start

**First time setup?** See [QUICK_START.md](QUICK_START.md) for detailed testing instructions.

### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ai4sr
   ```

2. **Set up environment**
   ```bash
   cp env.example .env
   # Edit .env and add your OpenAI API key:
   # OPENAI_KEY=your_api_key_here
   ```

3. **Run with Docker**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Open http://localhost:5001 in your browser
   - Click the ⚙️ Settings button to configure your API key
   - Start asking research questions!

### Option 2: Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Set up environment**
   ```bash
   cp env.example .env
   # Edit .env with your OpenAI API key
   ```

3. **Run the application**
   ```bash
   python run.py
   ```

4. **Access at http://localhost:5001** (default port)

## Usage

### Literature Review Mode
- Ask research questions like "What are the main causes of overdose in Eastern Europe?"
- The AI will search PubMed, screen papers, and provide relevant results
- Papers are scored and include detailed rationale for inclusion/exclusion

### RAG Chat Mode
- Upload and chat with your own research papers
- Ask questions about specific papers or research topics
- Get AI-powered insights from your document collection

### Settings
- Click the ⚙️ Settings button to:
  - Configure your OpenAI API key
  - Set default paper limits
  - Manage project preferences

## API Key Setup

**Important**: Your API key is stored locally in your browser and never sent to our servers.

1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Click the ⚙️ Settings button in the app
3. Enter your API key and click "Test API Key" to verify
4. Save settings to start using the application

## Docker Deployment

The application is fully containerized and ready for deployment:

```bash
# Build and run
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Project Structure

```
ai4sr/
├── agents/           # AI agents for literature review and RAG
├── webapp/           # Flask web application
├── db/              # Database schema and connection
├── static/          # Frontend assets (CSS, JS)
├── templates/       # HTML templates
├── data/            # Database and embeddings storage
└── docker-compose.yml
```

## Environment Variables

See `env.example` for all available configuration options. Key variables:

### Required (One of the following)
- `OPENAI_KEY`: Your OpenAI API key (if using OpenAI directly)
- `AZURE_EXISTING_AIPROJECT_ENDPOINT`: Azure AI Project endpoint (if using Azure)

### Production (Required in production)
- `FLASK_SECRET_KEY`: Secret key for Flask sessions (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)

### Optional
- `FLASK_HOST`: Host to bind to (default: `0.0.0.0`)
- `FLASK_PORT`: Port to run on (default: `5001`)
- `FLASK_DEBUG`: Enable debug mode (default: `False`, disabled in production)
- `FLASK_ENV`: Environment (`development` or `production`)
- `LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `LOG_FILE`: Path to log file (default: `logs/app.log`)
- `DB_PATH`: Database file path (default: `data/review.db`)

For Azure AI Projects integration, see `SETUP_AZURE.md`.

## Requirements

- Python 3.10+
- Either OpenAI API key OR Azure AI Projects configuration
- Docker (for containerized deployment)

**Note**: This application has been migrated to use Azure AI Projects. See `SETUP_AZURE.md` for Azure configuration.

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

## Development Setup

1. **Clone and install**
   ```bash
   git clone <repository-url>
   cd ai4sr
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Set up environment**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

3. **Run in development mode**
   ```bash
   FLASK_ENV=development FLASK_DEBUG=True python run.py
   ```

4. **Run tests** (when available)
   ```bash
   pytest
   ```

## Troubleshooting

### Docker Issues
- Ensure Docker Desktop is running
- Check logs: `docker-compose logs -f`
- Rebuild if needed: `docker-compose up --build`
- Check health: `curl http://localhost:5001/api/health`

### API Key Issues
- Verify your OpenAI API key is valid
- Check you have sufficient API credits
- Test the key in the Settings panel
- Check logs for authentication errors

### Database Issues
- The database is automatically initialized on first run
- Data persists in the `./data` directory
- If schema issues occur, delete `data/review.db` and restart

### Port Already in Use
- Change `FLASK_PORT` in `.env` to use a different port
- Or stop the existing process: `lsof -ti:5001 | xargs kill`

### Logging Issues
- Check `logs/app.log` for detailed error messages
- Set `LOG_LEVEL=DEBUG` for verbose logging
- Ensure `logs/` directory exists and is writable

### Production Deployment
- Set `FLASK_ENV=production` or `ENVIRONMENT=production`
- **Required**: Set `FLASK_SECRET_KEY` to a secure random value
- Debug mode is automatically disabled in production
- Use a production WSGI server (gunicorn) instead of Flask's dev server

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## License

This project is licensed under the MIT License.