FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package itself (needed for internal imports via pyproject.toml)
RUN pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5001

# Create required directories
RUN mkdir -p /app/data /app/logs && \
    chmod 755 /app/data /app/logs

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5001/api/health || exit 1

# Initialize database at build time (schema only, safe to re-run)
# At runtime, run.py also calls init_db() as a safety net
# Use gunicorn for production; run.py for development
CMD ["sh", "-c", "python -c 'from db.connection import init_db; init_db()' && gunicorn --bind 0.0.0.0:5001 --workers 2 --timeout 300 --access-logfile - 'webapp:create_app()'"]