# AI4SR Application Makefile
# Provides convenient commands for running and managing the application

.PHONY: help install run run-docker run-daemon stop clean init-db

# Default target
help:
	@echo "AI4SR Application Commands"
	@echo "========================="
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies"
	@echo "  init-db     Initialize the database"
	@echo ""
	@echo "Running:"
	@echo "  run         Run the application with Python"
	@echo "  run-docker  Run the application with Docker"
	@echo "  run-daemon  Run the application with Docker in background"
	@echo ""
	@echo "Management:"
	@echo "  stop        Stop Docker containers"
	@echo "  clean       Clean up Docker containers and images"
	@echo "  logs        View Docker logs"
	@echo ""
	@echo "Development:"
	@echo "  dev         Run in development mode with auto-reload"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Initialize database
init-db:
	@echo "Initializing database..."
	python scripts/init_db.py

# Run with Python
run:
	@echo "Starting AI4SR with Python..."
	python run.py

# Run with Docker
run-docker:
	@echo "Starting AI4SR with Docker..."
	docker-compose up --build

# Run with Docker in background
run-daemon:
	@echo "Starting AI4SR with Docker (detached)..."
	docker-compose up --build -d
	@echo "AI4SR is running in the background!"
	@echo "To view logs: make logs"
	@echo "To stop: make stop"

# Stop Docker containers
stop:
	@echo "Stopping Docker containers..."
	docker-compose down

# View Docker logs
logs:
	@echo "Viewing Docker logs..."
	docker-compose logs -f

# Clean up Docker
clean:
	@echo "Cleaning up Docker containers and images..."
	docker-compose down --rmi all --volumes --remove-orphans

# Development mode
dev:
	@echo "Starting AI4SR in development mode..."
	FLASK_ENV=development python run.py
