#!/usr/bin/env python3
"""
Simple run script for AI4SR application.
This script handles database initialization and starts the Flask app.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point for running the application."""
    # Set up logging first
    from utils.logger import setup_logging, get_logger
    logger = setup_logging(
        log_file=os.getenv("LOG_FILE", str(project_root / "logs" / "app.log"))
    )
    app_logger = get_logger("run")
    
    app_logger.info("Starting AI4SR Application...")
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if not env_file.exists():
        app_logger.warning(".env file not found. Please create one with your configuration.")
        app_logger.warning("Required: Either OPENAI_KEY or AZURE_EXISTING_AIPROJECT_ENDPOINT")
    
    # Import and run the app
    try:
        # Change to the project directory to ensure proper imports
        os.chdir(project_root)
        
        # Import the Flask app directly
        from webapp import create_app
        from db.connection import init_db
        from config import DB_PATH, validate_required_config, IS_PRODUCTION
        
        # Validate configuration
        if not validate_required_config():
            app_logger.error("Configuration validation failed. Exiting.")
            sys.exit(1)
        
        # Always try to initialize database (safe to run multiple times)
        # This ensures schema is up to date
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
        port = int(os.getenv('FLASK_PORT', '5001'))
        
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
