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
from config import DB_PATH, validate_required_config, IS_PRODUCTION
from utils.logger import setup_logging, get_logger

def main():
    """Main entry point for the application."""
    # Set up logging
    logger = setup_logging(
        log_file=os.getenv("LOG_FILE", str(project_root / "logs" / "app.log"))
    )
    app_logger = get_logger("webapp.app")
    
    # Validate configuration
    if not validate_required_config():
        app_logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)
    
    # Always try to initialize database (safe to run multiple times)
    try:
        if not os.path.exists(DB_PATH):
            app_logger.info(f"Database not found. Initializing at {DB_PATH}...")
        else:
            app_logger.info(f"Database found at {DB_PATH}. Verifying schema...")
        init_db()
    except Exception as e:
        app_logger.error(f"Database initialization failed: {e}")
        app_logger.warning("This might cause issues with the application.")
        # Continue anyway - maybe the database exists and is fine
    
    # Create Flask app
    app = create_app()
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5001'))  # Default to 5001 for consistency
    
    # Disable debug mode in production
    debug = False
    if not IS_PRODUCTION:
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    else:
        app_logger.warning("Debug mode disabled in production")
    
    app_logger.info(f"Starting AI4SR app on {host}:{port}")
    app_logger.info(f"Debug mode: {debug}")
    app_logger.info(f"Environment: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")
    
    # Run the app
    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    main()
