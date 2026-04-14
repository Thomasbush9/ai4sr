#!/usr/bin/env python3
"""
Test script for all AI4SR specialized agents using Azure AI Foundry.
Run with: python test_all_agents.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.azure_config import (
    chat_completion,
    AGENT_DEFINITIONS
)


def test_agent_creation():
    """Test that the Azure OpenAI client can be created and agent definitions exist."""
    print("\n" + "="*60)
    print("TEST 1: Client & Agent Definitions")
    print("="*60)

    from agents.azure_config import get_azure_client

    try:
        client = get_azure_client()
        print(f"Azure OpenAI client created: {client is not None}")
    except Exception as e:
        print(f"  [FAIL] Could not create Azure client: {e}")
        return False

    # Verify all agent definitions have required keys
    for agent_type, defn in AGENT_DEFINITIONS.items():
        if "name" not in defn or "instructions" not in defn:
            print(f"  [FAIL] Agent definition '{agent_type}' missing name or instructions")
            return False
        print(f"  [OK] Agent definition: {defn['name']} (type: {agent_type})")

    return True


def test_pico_agent():
    """Test the PICO expansion agent."""
    print("\n" + "="*60)
    print("TEST 2: PICO Agent")
    print("="*60)

    pico_description = "Population: Adults with type 2 diabetes | Intervention: SGLT2 inhibitors | Outcome: HbA1c reduction"

    prompt = f"""Expand this PICO framework description into search queries.

PICO Description: {pico_description}

Provide:
1. question_summary: 1-sentence summary
2. pubmed_query: Boolean search query for PubMed
3. openalex_query: Simple text query for OpenAlex
4. pico_keywords: JSON object with keywords

Respond in JSON format."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="pico")
        print(f"Response:\n{response[:500]}...")
        return True
    except Exception as e:
        print(f"[FAIL] PICO agent error: {e}")
        return False


def test_screener_agent():
    """Test the screening agent."""
    print("\n" + "="*60)
    print("TEST 3: Screener Agent")
    print("="*60)

    prompt = """First-pass triage of a study's title and abstract.

Research question: Do SGLT2 inhibitors reduce cardiovascular events in diabetic patients?
Title: Empagliflozin and Cardiovascular Outcomes in Patients with Type 2 Diabetes
Abstract: In this randomized trial, empagliflozin significantly reduced cardiovascular death and hospitalization for heart failure in patients with type 2 diabetes at high cardiovascular risk.

Respond in JSON format with keys: "decision" (include/maybe/exclude) and "score" (0-100)."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="screener")
        print(f"Response:\n{response}")
        return True
    except Exception as e:
        print(f"[FAIL] Screener agent error: {e}")
        return False


def test_keyword_agent():
    """Test the keyword expansion agent."""
    print("\n" + "="*60)
    print("TEST 4: Keyword Agent")
    print("="*60)

    prompt = """Expand this research question into keywords and boolean search strings.

Research question: What is the effect of SGLT2 inhibitors on heart failure outcomes?

Provide:
1. A JSON list of short keywords/synonyms
2. A boolean string with AND/OR and parentheses
3. A PubMed-ready Boolean string

Respond in JSON format with keys: "keywords_json", "boolean_generic", "boolean_pubmed"."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="keyword")
        print(f"Response:\n{response[:500]}...")
        return True
    except Exception as e:
        print(f"[FAIL] Keyword agent error: {e}")
        return False


def test_review_agent():
    """Test the review agent."""
    print("\n" + "="*60)
    print("TEST 5: Review Agent")
    print("="*60)

    prompt = """Extract structured information from this research paper.

Title: Dapagliflozin and Cardiovascular Outcomes in Type 2 Diabetes
Abstract: This multicenter, randomized, double-blind trial evaluated the effects of dapagliflozin on cardiovascular outcomes in 17,160 patients with type 2 diabetes. Dapagliflozin reduced the risk of the composite outcome of cardiovascular death or hospitalization for heart failure by 17%.

Extract:
- population: Population studied
- intervention: Intervention or treatment
- comparator: Comparison or control group
- outcomes: Outcomes measured
- main_findings: Main findings
- sample_size: Sample size

Respond in JSON format."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="review")
        print(f"Response:\n{response}")
        return True
    except Exception as e:
        print(f"[FAIL] Review agent error: {e}")
        return False


def test_cot_screener_agent():
    """Test the chain-of-thought screener agent."""
    print("\n" + "="*60)
    print("TEST 6: CoT Screener Agent")
    print("="*60)

    prompt = """Perform detailed PICO analysis for systematic review inclusion.

Research question: Do SGLT2 inhibitors reduce hospitalization in patients with heart failure?
Title: Effect of Empagliflozin on Hospitalization in Patients With Heart Failure
Abstract: This study examined the effects of empagliflozin on hospitalization rates. 4,744 patients with heart failure were randomized to empagliflozin or placebo. Empagliflozin reduced heart failure hospitalizations by 30%.

Analyze using PICO framework and provide decision with rationale.
Respond in JSON format with keys: "decision" (include/maybe/exclude) and "rationale"."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="cot-screener")
        print(f"Response:\n{response}")
        return True
    except Exception as e:
        print(f"[FAIL] CoT Screener agent error: {e}")
        return False


def test_cold_start_agent():
    """Test the cold-start agent."""
    print("\n" + "="*60)
    print("TEST 7: Cold-Start Agent")
    print("="*60)

    prompt = """Screen this paper for systematic review inclusion based on PICO criteria.

PICO Description: Population: Adults with heart failure | Intervention: SGLT2 inhibitors | Outcome: Hospitalization rates
Title: Canagliflozin and Heart Failure Outcomes: A Randomized Trial
Abstract: We investigated the effects of canagliflozin on heart failure outcomes in a randomized controlled trial of 10,142 patients.

Decide if the paper should be INCLUDED or EXCLUDED.
Respond in JSON format with keys: "decision" (INCLUDE or EXCLUDE) and "rationale"."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="cold-start")
        print(f"Response:\n{response}")
        return True
    except Exception as e:
        print(f"[FAIL] Cold-start agent error: {e}")
        return False


def test_rag_agent():
    """Test the RAG agent."""
    print("\n" + "="*60)
    print("TEST 8: RAG Agent")
    print("="*60)

    prompt = """Answer the following question using the provided context from literature review papers.

Question: What is the effect of SGLT2 inhibitors on heart failure?

Context:
Paper 1:
Title: Empagliflozin and Heart Failure Outcomes
Abstract: Empagliflozin reduced cardiovascular death by 38% and hospitalization for heart failure by 35%.

Paper 2:
Title: Dapagliflozin in Heart Failure
Abstract: Dapagliflozin reduced the combined outcome of worsening heart failure or cardiovascular death by 26%.

Provide a comprehensive answer based on the context."""

    try:
        response = chat_completion([{"role": "user", "content": prompt}], agent_type="rag")
        print(f"Response:\n{response[:500]}...")
        return True
    except Exception as e:
        print(f"[FAIL] RAG agent error: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("AI4SR Agent Test Suite")
    print("="*60)
    print(f"Endpoint: {os.getenv('AZURE_EXISTING_AIPROJECT_ENDPOINT', 'NOT SET')}")
    print(f"Model: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4.1')}")

    results = []

    # Run all tests
    tests = [
        ("Agent Creation", test_agent_creation),
        ("PICO Agent", test_pico_agent),
        ("Screener Agent", test_screener_agent),
        ("Keyword Agent", test_keyword_agent),
        ("Review Agent", test_review_agent),
        ("CoT Screener Agent", test_cot_screener_agent),
        ("Cold-Start Agent", test_cold_start_agent),
        ("RAG Agent", test_rag_agent),
    ]

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"[FAIL] {name} raised exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
