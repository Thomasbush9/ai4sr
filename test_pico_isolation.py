#!/usr/bin/env python3
"""
Minimal test to isolate PICO expansion issue.
Run with: python test_pico_isolation.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.azure_config import (
    get_azure_client,
    chat_completion
)


def test_azure_client():
    """Test Azure OpenAI client creation."""
    print("\n" + "="*60)
    print("TEST 1: Azure OpenAI Client")
    print("="*60)
    try:
        client = get_azure_client()
        print(f"✓ Azure client created: {type(client).__name__}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_api_call():
    """Test API call with minimal prompt."""
    print("\n" + "="*60)
    print("TEST 4: API Call")
    print("="*60)
    try:
        messages = [{"role": "user", "content": "Say 'hello' in one word"}]
        print("Calling chat_completion with timeout=30s...")
        response = chat_completion(messages, agent_type="pico", timeout=30)
        print(f"✓ Response received: {response[:100]}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pico_expansion():
    """Test PICO expansion end-to-end."""
    print("\n" + "="*60)
    print("TEST 5: PICO Expansion")
    print("="*60)
    try:
        from agents.pico import PICOExpansionProgram
        
        pico_description = "Population: Adults with heart failure | Intervention: SGLT2 inhibitors | Comparison: Placebo | Outcome: Hospitalization"
        
        program = PICOExpansionProgram()
        print("Calling PICO expansion...")
        result = program.forward(pico_description)
        print(f"✓ PICO expansion completed")
        print(f"  Question summary: {result.get('question_summary', '')[:50]}...")
        print(f"  PubMed query: {result.get('pubmed_query', '')[:50]}...")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PICO EXPANSION ISOLATION TEST")
    print("="*60)
    
    results = {}
    results['azure_client'] = test_azure_client()

    if results['azure_client']:
        results['api_call'] = test_api_call()

        if results['api_call']:
            results['pico_expansion'] = test_pico_expansion()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed. Check logs above.")
    
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if main() else 1)


