#!/usr/bin/env python3
"""
Test script to verify Azure OpenAI and Microsoft Authentication setup.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_environment_variables():
    """Check if all required environment variables are set."""
    print("\n" + "="*60)
    print("1. ENVIRONMENT VARIABLES CHECK")
    print("="*60)

    required_vars = {
        "Azure AI Projects": [
            "AZURE_EXISTING_AIPROJECT_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
        ],
        "Microsoft Auth (Optional)": [
            "MICROSOFT_CLIENT_ID",
            "MICROSOFT_CLIENT_SECRET",
            "MICROSOFT_TENANT_ID",
        ]
    }

    all_set = True
    for category, vars_list in required_vars.items():
        print(f"\n{category}:")
        for var in vars_list:
            value = os.getenv(var)
            if value:
                # Show partial value for security
                if "KEY" in var or "SECRET" in var:
                    display = f"{value[:10]}..." if len(value) > 10 else "***"
                else:
                    display = value[:50] + "..." if len(value) > 50 else value
                print(f"  ✓ {var}: {display}")
            else:
                print(f"  ✗ {var}: NOT SET")
                if "Azure" in category:
                    all_set = False

    return all_set


def test_azure_openai():
    """Test Azure OpenAI connection."""
    print("\n" + "="*60)
    print("2. AZURE OPENAI CONNECTION TEST")
    print("="*60)

    try:
        from agents.azure_config import chat_completion

        print("\n  Testing chat completion...")
        messages = [{"role": "user", "content": "Say 'hello' in one word"}]
        response = chat_completion(messages, max_tokens=5, temperature=0.1)

        print(f"  ✓ Chat completion successful!")
        print(f"  Response: {response}")
        return True

    except Exception as e:
        print(f"  ✗ Chat completion failed: {str(e)}")
        return False


def test_embeddings():
    """Test Azure OpenAI embeddings."""
    print("\n" + "="*60)
    print("3. AZURE OPENAI EMBEDDINGS TEST")
    print("="*60)

    try:
        from agents.azure_config import get_embedding

        print("\n  Testing embeddings...")
        embedding = get_embedding("test text")

        print(f"  ✓ Embeddings successful!")
        print(f"  Embedding dimension: {len(embedding)}")
        return True

    except Exception as e:
        print(f"  ✗ Embeddings failed: {str(e)}")
        return False


def test_agent_imports():
    """Test that all agents can be imported."""
    print("\n" + "="*60)
    print("4. AGENT IMPORTS TEST")
    print("="*60)

    agents = [
        "screening",
        "keyword_exp",
        "pico",
        "review_agent",
        "cold_start_agent",
        "rag_agent",
        "orchestrator"
    ]

    all_imported = True
    for agent_name in agents:
        try:
            __import__(f"agents.{agent_name}")
            print(f"  ✓ agents.{agent_name}")
        except Exception as e:
            print(f"  ✗ agents.{agent_name}: {str(e)}")
            all_imported = False

    return all_imported


def test_flask_app():
    """Test that Flask app can be created."""
    print("\n" + "="*60)
    print("5. FLASK APP TEST")
    print("="*60)

    try:
        from webapp import create_app
        app = create_app()
        print(f"  ✓ Flask app created successfully")
        print(f"  Routes registered: {len(app.url_map._rules)}")
        return True
    except Exception as e:
        print(f"  ✗ Flask app creation failed: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AZURE MIGRATION TEST SUITE")
    print("="*60)

    results = {}

    # Test 1: Environment variables
    results['env'] = test_environment_variables()

    if not results['env']:
        print("\n" + "="*60)
        print("⚠️  AZURE CREDENTIALS NOT CONFIGURED")
        print("="*60)
        print("\nPlease set up your Azure AI Projects credentials in .env file:")
        print("  - AZURE_EXISTING_AIPROJECT_ENDPOINT")
        print("  - AZURE_OPENAI_DEPLOYMENT_NAME")
        print("  - AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
        print("\nAnd authenticate with: az login")
        print("\nSee .env.example for template.")
        print("\nSkipping Azure API tests...\n")
    else:
        # Test 2: Azure OpenAI chat
        results['chat'] = test_azure_openai()

        # Test 3: Azure OpenAI embeddings
        results['embeddings'] = test_embeddings()

    # Test 4: Agent imports
    results['agents'] = test_agent_imports()

    # Test 5: Flask app
    results['flask'] = test_flask_app()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed! Ready to run the application.")
    elif results.get('agents') and results.get('flask'):
        print("\n⚠️  Core functionality working, but Azure API tests failed.")
        print("   Please configure Azure OpenAI credentials to enable AI features.")
    else:
        print("\n❌ Some tests failed. Please review errors above.")

    return passed == total


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
