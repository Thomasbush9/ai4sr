#!/usr/bin/env python3
"""
Main application entry point for AI4SR Flask app.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp import create_app
from db.connection import init_db
from config import DB_PATH

def main():
    """Main entry point for the application."""
    # Always try to initialize database (safe to run multiple times)
    try:
        if not os.path.exists(DB_PATH):
            print(f"📊 Database not found. Initializing at {DB_PATH}...")
        else:
            print(f"📊 Database found at {DB_PATH}. Verifying schema...")
        init_db()
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("   This might cause issues with the application.")
        # Continue anyway - maybe the database exists and is fine
    
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

if __name__ == "__main__":
    main()
