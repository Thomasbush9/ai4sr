#!/usr/bin/env python3
"""
Simple test script to verify AI4SR application setup.
Run this after setup to ensure everything is configured correctly.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all critical modules can be imported."""
    print("Testing imports...")
    try:
        import config
        from webapp import create_app
        from db.connection import init_db
        from utils.logger import get_logger
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_config():
    """Test configuration validation."""
    print("\nTesting configuration...")
    try:
        from config import validate_required_config, IS_PRODUCTION
        
        if validate_required_config():
            print("✓ Configuration valid")
        else:
            print("✗ Configuration validation failed")
            return False
        
        print(f"  Environment: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")
        
        # Check OpenAI key or Azure config
        if os.getenv("OPENAI_KEY"):
            print("  ✓ OPENAI_KEY is set")
        elif os.getenv("AZURE_EXISTING_AIPROJECT_ENDPOINT"):
            print("  ✓ AZURE_EXISTING_AIPROJECT_ENDPOINT is set")
        else:
            print("  ⚠ Neither OPENAI_KEY nor AZURE_EXISTING_AIPROJECT_ENDPOINT is set")
            print("     (One of these is required for full functionality)")
        
        # Check secret key in production
        if IS_PRODUCTION:
            if os.getenv("FLASK_SECRET_KEY"):
                print("  ✓ FLASK_SECRET_KEY is set (required in production)")
            else:
                print("  ✗ FLASK_SECRET_KEY not set (REQUIRED in production)")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_database():
    """Test database initialization."""
    print("\nTesting database...")
    try:
        from db.connection import init_db
        from config import DB_PATH
        
        init_db()
        if DB_PATH.exists():
            print(f"✓ Database initialized at {DB_PATH}")
            return True
        else:
            print(f"✗ Database file not found at {DB_PATH}")
            return False
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

def test_flask_app():
    """Test Flask app creation."""
    print("\nTesting Flask app...")
    try:
        from webapp import create_app
        
        app = create_app()
        print("✓ Flask app created successfully")
        
        # Test health endpoint
        with app.test_client() as client:
            response = client.get('/api/health')
            if response.status_code == 200:
                print("✓ Health check endpoint working")
                return True
            else:
                print(f"✗ Health check returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Flask app test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_logging():
    """Test logging setup."""
    print("\nTesting logging...")
    try:
        from utils.logger import get_logger
        
        logger = get_logger("test")
        logger.info("Test log message")
        print("✓ Logging system working")
        return True
    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("AI4SR Application Test Suite")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Logging", test_logging),
        ("Flask App", test_flask_app),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Application is ready to use.")
        print("\nTo start the application, run:")
        print("  python run.py")
        return 0
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

