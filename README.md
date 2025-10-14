# AI4SR: AI-Powered Systematic Review Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI4SR is an intelligent literature review assistant that streamlines the systematic review process using advanced AI techniques. It combines automated paper discovery, intelligent screening, and question-answering capabilities to help researchers efficiently conduct comprehensive literature reviews.

## 🌟 Features

### 🔍 **Intelligent Literature Discovery**
- **Automated Paper Search**: Searches PubMed and other academic databases using AI-generated keywords and concepts
- **Smart Query Expansion**: Automatically expands research queries with synonyms and related concepts
- **Multi-source Integration**: Fetches papers from multiple academic sources with comprehensive metadata

### 🤖 **AI-Powered Screening**
- **Automated Relevance Assessment**: Uses advanced language models to evaluate paper relevance
- **Intelligent Scoring**: Provides confidence scores (0-100) for each paper
- **Detailed Rationale**: Explains screening decisions with clear reasoning
- **Batch Processing**: Efficiently processes large sets of papers

### 💬 **Interactive Q&A System**
- **RAG-based Question Answering**: Retrieval-Augmented Generation for accurate, context-aware responses
- **Project-specific Knowledge**: Answers questions based on your curated paper collection
- **Conversation History**: Maintains context across multiple questions
- **Dual Modes**: Switch between literature discovery and Q&A seamlessly

### 📊 **Project Management**
- **Multi-project Support**: Organize different research topics in separate projects
- **Comprehensive Database**: SQLite-based storage with full-text search capabilities
- **Export Capabilities**: Easy data export for further analysis
- **Progress Tracking**: Monitor your review progress with detailed statistics

## 🚀 Quick Start

### 🐳 Docker Quick Start (Easiest - Recommended for Shipping)

The fastest way to get AI4SR running with zero dependency issues:

1. **Clone and configure:**
   ```bash
   git clone https://github.com/your-username/ai4sr.git
   cd ai4sr
   cp env.example .env
   # Edit .env and add your OpenAI API key
   ```

2. **Run with Docker:**
   ```bash
   docker-compose up --build
   ```

3. **Access the app:**
   Open `http://localhost:5000` in your browser

That's it! Docker handles all dependencies, Python version, and setup automatically.

### Prerequisites

- **For Docker:** Docker and Docker Compose installed
- **For standard Python:** Python 3.10 or higher
- **For both:** OpenAI API key (get from https://platform.openai.com/api-keys)
- Internet connection (for paper fetching)

### ⚡ Super Quick Start (2 minutes)

1. **Clone and setup:**
   ```bash
   git clone https://github.com/your-username/ai4sr.git
   cd ai4sr
   pip install -e .
   ```

2. **Add your OpenAI API key:**
   ```bash
   echo "OPENAI_KEY=your_openai_api_key_here" > .env
   ```

3. **Run the application:**
   ```bash
   python run.py
   ```

4. **Open your browser:**
   Go to `http://localhost:5000` (or `http://localhost:5001` if port 5000 is busy)

That's it! The database will be automatically initialized and you can start using the AI4SR systematic review assistant.

### ✅ Verified Working Features

Based on the terminal output, the following features are confirmed working:

- **✅ Literature Review Mode**: Successfully searches and retrieves papers from PubMed
- **✅ RAG Q&A Mode**: Answers questions based on your paper collection
- **✅ Project Management**: Creates and manages multiple research projects
- **✅ Database Operations**: Automatic initialization and data persistence
- **✅ API Endpoints**: RESTful API for frontend communication
- **✅ Paper Processing**: Handles PDFs, abstracts, and metadata
- **✅ AI Integration**: OpenAI GPT models for intelligent analysis

**Example working session:**
```
DEBUG: RAG answering question: 'what are good prevention for social media addiction?' for project 5
DEBUG: Loading papers from SQLite database...
DEBUG: Project 5 has 5 papers
DEBUG: Retrieved 5 most relevant papers
DEBUG: RAG answer generated successfully
```

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ai4sr.git
   cd ai4sr
   ```

2. **Install dependencies**
   ```bash
   # Option 1: Using pip
   pip install -r requirements.txt
   
   # Option 2: Using uv (recommended)
   uv pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   echo "OPENAI_KEY=your_openai_api_key_here" >> .env
   ```

4. **Run the application (Multiple Options)**

   **Option A: Simple Python runner (Recommended)**
   ```bash
   python run.py
   ```

   **Option B: Using the shell script**
   ```bash
   ./run.sh
   # or
   ./run.sh python
   ```

   **Option C: Using Make**
   ```bash
   make run
   ```

   **Option D: Direct Flask command**
   ```bash
   python -m webapp.app
   ```

5. **Access the web interface**
   Open your browser and navigate to `http://localhost:5000`
   
   **Note**: If port 5000 is busy (common on macOS due to AirPlay Receiver), the app will automatically use port 5001 or you can specify a port:
   ```bash
   FLASK_PORT=5001 python run.py
   ```

   **Note**: The database will be automatically initialized on first run if it doesn't exist.

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

1. **Set up environment**
   ```bash
   cp env.example .env
   # Add your OpenAI API key to .env
   ```

2. **Run with Docker (Multiple Options)**

   **Option A: Using the shell script**
   ```bash
   ./run.sh docker
   ```

   **Option B: Using Make**
   ```bash
   make run-docker
   ```

   **Option C: Direct Docker Compose**
   ```bash
   docker-compose up --build
   ```

   **Option D: Run in background**
   ```bash
   ./run.sh daemon
   # or
   make run-daemon
   ```

3. **Access the application**
   Navigate to `http://localhost:5000` (or `http://localhost:5001` if port 5000 is busy)

4. **Manage Docker containers**
   ```bash
   # View logs
   make logs
   # or
   docker-compose logs -f

   # Stop containers
   make stop
   # or
   docker-compose down

   # Clean up everything
   make clean
   ```

### Manual Docker Build

```bash
docker build -t ai4sr .
docker run -p 5000:5000 --env-file .env -v $(pwd)/data:/app/data ai4sr
```

## 🔧 Troubleshooting

### Common Issues

**Port 5000 already in use:**
```bash
# Use a different port
FLASK_PORT=5001 python run.py

# Or disable AirPlay Receiver on macOS:
# System Preferences → General → AirDrop & Handoff → AirPlay Receiver → Off
```

**Import errors:**
```bash
# Make sure the package is installed in development mode
pip install -e .

# Or install dependencies manually
pip install -r requirements.txt
```

**Database issues:**
```bash
# Manually initialize the database
python scripts/init_db.py
```

**Missing dependencies:**
```bash
# Install all dependencies
pip install -r requirements.txt
pip install metapub==0.6.4  # Additional dependency for PubMed access
```

### Docker Issues

**Docker daemon not running:**
```bash
# On macOS/Windows: Start Docker Desktop
# On Linux: 
sudo systemctl start docker
```

**Port conflicts in Docker:**
```bash
# Edit docker-compose.yml to change the port mapping:
# Change "5000:5000" to "5001:5000" (or any available port)
```

**Permission issues with data directory:**
```bash
# Ensure the data directory has proper permissions
chmod -R 755 data/
```

**Rebuilding after changes:**
```bash
# Force rebuild and restart
docker-compose down
docker-compose up --build --force-recreate
```

**View Docker logs:**
```bash
# See what's happening inside the container
docker-compose logs -f
```

### Environment Variables

Create a `.env` file in the project root with:
```bash
OPENAI_KEY=your_openai_api_key_here
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

## 📖 Usage Guide

### 1. Literature Review Mode

**Start a new review:**
1. Select "Literature Review" mode
2. Enter your research question or topic
3. Specify the number of papers to retrieve (1-50)
4. Click "Send" to begin the automated search

**The system will:**
- Generate relevant keywords and concepts
- Search academic databases
- Screen papers for relevance
- Provide detailed results with scores and rationale

### 2. Q&A Mode

**Ask questions about your papers:**
1. Switch to "Q&A" mode
2. Ask specific questions about your research
3. Get AI-powered answers based on your paper collection
4. Maintain conversation context across multiple questions

### 3. Project Management

**Create and manage projects:**
- Each project maintains its own paper collection
- Switch between projects to work on different research topics
- View project statistics and progress

## 🏗️ Architecture

### Core Components

- **Orchestrator** (`agents/orchestrator.py`): Main coordination logic
- **Paper Finder** (`agents/paper_finder.py`): Academic database integration
- **RAG Agent** (`agents/rag_agent.py`): Question-answering system
- **Screening Agent** (`agents/screening.py`): Paper relevance assessment
- **Web Interface** (`webapp/`): Flask-based user interface

### Technology Stack

- **Backend**: Python, Flask, SQLite
- **AI/ML**: DSPy, OpenAI GPT models, FAISS vector search
- **Data Processing**: Pandas, NumPy
- **Web**: HTML5, CSS3, JavaScript
- **Deployment**: Docker, Docker Compose

### Database Schema

The system uses SQLite with the following key tables:
- `projects`: Research project management
- `papers`: Paper metadata and screening results
- `conversations`: Chat history
- `messages`: Individual conversation messages

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Required
OPENAI_KEY=your_openai_api_key_here

# Optional
DB_PATH=./data/review.db
DATA_DIR=./data
```

### API Configuration

The system supports various AI models through the DSPy framework:
- **Default**: GPT-4o-mini for cost efficiency
- **Embeddings**: OpenAI text-embedding-3-small
- **Customizable**: Modify model settings in `agents/rag_agent.py`

## 📊 Performance & Limits

- **Paper Retrieval**: 1-50 papers per search (configurable)
- **Screening**: Batch processing for efficiency
- **Storage**: SQLite database with full-text search
- **API Limits**: Respects OpenAI rate limits with built-in retry logic

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Run tests:
   ```bash
   python -m pytest tests/
   ```
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [DSPy](https://github.com/stanfordnlp/dspy) for AI pipeline management
- Uses [FAISS](https://github.com/facebookresearch/faiss) for vector similarity search
- Integrates with [PubMed](https://pubmed.ncbi.nlm.nih.gov/) and other academic databases
- Powered by OpenAI's language models

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/ai4sr/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/ai4sr/discussions)
- **Documentation**: [Wiki](https://github.com/your-username/ai4sr/wiki)

## 🔮 Roadmap

- [ ] Support for additional academic databases
- [ ] Advanced analytics and visualization
- [ ] Collaborative review features
- [ ] Export to popular reference managers
- [ ] Integration with systematic review tools
- [ ] Multi-language support

---
