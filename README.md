# AI4SR - Literature Review Assistant

An AI-powered literature review assistant that helps researchers find, analyze, and organize academic papers using advanced language models and semantic search.

## Features

- **Literature Review Mode**: Automated paper discovery and screening using AI
- **RAG Chat Mode**: Interactive Q&A about your research papers
- **Project Management**: Organize papers by research projects
- **Smart Screening**: AI-powered relevance scoring and rationale
- **Docker Support**: Easy deployment and distribution

## Quick Start

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

4. **Access at http://localhost:5000**

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

## Requirements

- Python 3.10+
- OpenAI API key
- Docker (for containerized deployment)

## Troubleshooting

### Docker Issues
- Ensure Docker Desktop is running
- Check logs: `docker-compose logs -f`
- Rebuild if needed: `docker-compose up --build`

### API Key Issues
- Verify your OpenAI API key is valid
- Check you have sufficient API credits
- Test the key in the Settings panel

### Database Issues
- The database is automatically initialized on first run
- Data persists in the `./data` directory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## License

This project is licensed under the MIT License.