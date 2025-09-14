#!/bin/bash

# AI4SR Application Runner
# This script provides easy ways to run the AI4SR application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Please create one with your configuration."
    print_status "Required variables: OPENAI_KEY"
fi

# Function to run with Python
run_python() {
    print_status "Starting AI4SR with Python..."
    python run.py
}

# Function to run with Docker
run_docker() {
    print_status "Starting AI4SR with Docker..."
    docker-compose up --build
}

# Function to run with Docker in background
run_docker_detached() {
    print_status "Starting AI4SR with Docker (detached)..."
    docker-compose up --build -d
    print_success "AI4SR is running in the background!"
    print_status "To view logs: docker-compose logs -f"
    print_status "To stop: docker-compose down"
}

# Function to show help
show_help() {
    echo "AI4SR Application Runner"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  python, p     Run with Python (default)"
    echo "  docker, d     Run with Docker"
    echo "  daemon, da    Run with Docker in background"
    echo "  help, h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0            # Run with Python"
    echo "  $0 python     # Run with Python"
    echo "  $0 docker     # Run with Docker"
    echo "  $0 daemon     # Run with Docker in background"
}

# Main script logic
case "${1:-python}" in
    python|p)
        run_python
        ;;
    docker|d)
        run_docker
        ;;
    daemon|da)
        run_docker_detached
        ;;
    help|h)
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
