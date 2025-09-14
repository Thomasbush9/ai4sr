#!/usr/bin/env python3
"""
Simple run script for AI4SR application.
This script handles database initialization and starts the Flask app.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point for running the application."""
    print("🚀 Starting AI4SR Application...")
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  Warning: .env file not found. Please create one with your configuration.")
        print("   Required variables: OPENAI_KEY")
    
    # Import and run the app
    try:
        # Change to the project directory to ensure proper imports
        os.chdir(project_root)
        
        # Import the Flask app directly
        from webapp import create_app
        from db.connection import init_db
        from config import DB_PATH
        
        # Initialize database if it doesn't exist
        if not os.path.exists(DB_PATH):
            print(f"Initializing database at {DB_PATH}")
            init_db()
            print("Database initialized successfully!")
        
        # Create Flask app
        app = create_app()
        
        # Get configuration from environment
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', '5000'))
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        print(f"Starting AI4SR app on {host}:{port}")
        print(f"Debug mode: {debug}")
        
        # Run the app
        app.run(host=host, port=port, debug=debug)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        print("  pip install -e .")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
