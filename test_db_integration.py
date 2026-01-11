#!/usr/bin/env python3
"""
Test database integration with Azure AI Foundry agents.
Run with: python test_db_integration.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import connect, init_db
from db.repository import (
    get_or_create_project,
    save_pico,
    get_pico,
    save_pico_expansion,
    get_pico_expansion,
    bulk_insert_unscreened,
    list_included,
    list_maybe,
    save_screening_labels,
    get_screening_stats,
    save_agent_summary,
    get_agent_summaries,
)
from agents.pico import PICO, pico_to_description, PICOExpansionProgram
from agents.screening import Screener, CoTScreener
from agents.cold_start_agent import ColdStartAgent
from agents.review_agent import ReviewAgent


def test_db_init():
    """Test database initialization."""
    print("\n" + "="*60)
    print("TEST 1: Database Initialization")
    print("="*60)

    try:
        init_db()
        print("[OK] Database initialized successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Database init failed: {e}")
        return False


def test_project_creation():
    """Test project creation."""
    print("\n" + "="*60)
    print("TEST 2: Project Creation")
    print("="*60)

    try:
        with connect() as con:
            project_id = get_or_create_project(con, "test-azure-agents")
            con.commit()
        print(f"[OK] Project created with ID: {project_id}")
        return project_id
    except Exception as e:
        print(f"[FAIL] Project creation failed: {e}")
        return None


def test_pico_save_and_retrieve(project_id: int):
    """Test saving and retrieving PICO."""
    print("\n" + "="*60)
    print("TEST 3: PICO Save and Retrieve")
    print("="*60)

    try:
        pico = PICO(
            population="Adults with type 2 diabetes",
            intervention="SGLT2 inhibitors",
            comparison="Placebo or standard care",
            outcome="HbA1c reduction and cardiovascular outcomes",
            study_design="Randomized controlled trials"
        )

        with connect() as con:
            pico_id = save_pico(con, project_id, pico)
            con.commit()
        print(f"[OK] PICO saved with ID: {pico_id}")

        with connect() as con:
            retrieved_pico = get_pico(con, project_id)

        if retrieved_pico and retrieved_pico.population == pico.population:
            print(f"[OK] PICO retrieved successfully")
            return True
        else:
            print(f"[FAIL] PICO retrieval mismatch")
            return False
    except Exception as e:
        print(f"[FAIL] PICO save/retrieve failed: {e}")
        return False


def test_pico_expansion(project_id: int):
    """Test PICO expansion with Azure agent."""
    print("\n" + "="*60)
    print("TEST 4: PICO Expansion with Azure Agent")
    print("="*60)

    try:
        with connect() as con:
            pico = get_pico(con, project_id)

        pico_description = pico_to_description(pico)
        print(f"PICO Description: {pico_description}")

        expansion_program = PICOExpansionProgram()
        expansion_result = expansion_program.forward(pico_description)

        print(f"Question Summary: {expansion_result.get('question_summary', '')[:100]}...")
        print(f"PubMed Query: {expansion_result.get('pubmed_query', '')[:100]}...")

        with connect() as con:
            save_pico_expansion(con, project_id, expansion_result)
            con.commit()
        print("[OK] PICO expansion saved successfully")

        with connect() as con:
            retrieved_expansion = get_pico_expansion(con, project_id)

        if retrieved_expansion and retrieved_expansion.get("question_summary"):
            print("[OK] PICO expansion retrieved successfully")
            return True
        else:
            print("[FAIL] PICO expansion retrieval failed")
            return False
    except Exception as e:
        print(f"[FAIL] PICO expansion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_paper_insertion(project_id: int):
    """Test paper insertion."""
    print("\n" + "="*60)
    print("TEST 5: Paper Insertion")
    print("="*60)

    sample_papers = [
        {
            "title": "Empagliflozin and Cardiovascular Outcomes in Patients with Type 2 Diabetes",
            "abstract": "In patients with type 2 diabetes at high cardiovascular risk, empagliflozin reduced cardiovascular death and hospitalization for heart failure.",
            "authors": "Zinman B, Wanner C, Lachin JM, et al.",
            "year": 2015,
            "venue": "New England Journal of Medicine",
            "doi": "10.1056/NEJMoa1504720",
            "pmid": "26378978"
        },
        {
            "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
            "abstract": "In patients with heart failure and reduced ejection fraction, dapagliflozin reduced the risk of worsening heart failure or cardiovascular death.",
            "authors": "McMurray JJV, Solomon SD, Inzucchi SE, et al.",
            "year": 2019,
            "venue": "New England Journal of Medicine",
            "doi": "10.1056/NEJMoa1911303",
            "pmid": "31535829"
        },
        {
            "title": "Canagliflozin and Cardiovascular and Renal Events in Type 2 Diabetes",
            "abstract": "Canagliflozin reduced cardiovascular events and renal outcomes in patients with type 2 diabetes.",
            "authors": "Neal B, Perkovic V, Mahaffey KW, et al.",
            "year": 2017,
            "venue": "New England Journal of Medicine",
            "doi": "10.1056/NEJMoa1611925",
            "pmid": "28605608"
        }
    ]

    try:
        with connect() as con:
            count = bulk_insert_unscreened(con, project_id, sample_papers)
            con.commit()
        print(f"[OK] Inserted {count} papers")
        return count > 0
    except Exception as e:
        print(f"[FAIL] Paper insertion failed: {e}")
        return False


def test_screening(project_id: int):
    """Test paper screening with Azure agent."""
    print("\n" + "="*60)
    print("TEST 6: Paper Screening with Azure Agent")
    print("="*60)

    try:
        screener = Screener()

        title = "Empagliflozin and Cardiovascular Outcomes in Patients with Type 2 Diabetes"
        abstract = "In patients with type 2 diabetes at high cardiovascular risk, empagliflozin reduced cardiovascular death."
        question = "Do SGLT2 inhibitors reduce cardiovascular events in type 2 diabetes?"

        result = screener.forward(question=question, title=title, abstract=abstract)
        print(f"Decision: {result.get('decision')}")
        print(f"Score: {result.get('score')}")

        if result.get('decision') in ['include', 'maybe', 'exclude']:
            print("[OK] Screening completed successfully")
            return True
        else:
            print("[FAIL] Invalid screening result")
            return False
    except Exception as e:
        print(f"[FAIL] Screening failed: {e}")
        return False


def test_cot_screening(project_id: int):
    """Test CoT screening with Azure agent."""
    print("\n" + "="*60)
    print("TEST 7: CoT Screening with Azure Agent")
    print("="*60)

    try:
        cot_screener = CoTScreener()

        title = "Dapagliflozin in Patients with Heart Failure"
        abstract = "Dapagliflozin reduced the risk of worsening heart failure or cardiovascular death in patients with heart failure."
        question = "Do SGLT2 inhibitors reduce hospitalization in heart failure patients?"

        result = cot_screener.forward(question=question, title=title, abstract=abstract)
        print(f"Decision: {result.get('decision')}")
        print(f"Rationale: {result.get('rationale', '')[:200]}...")

        if result.get('decision') in ['include', 'maybe', 'exclude']:
            print("[OK] CoT screening completed successfully")
            return True
        else:
            print("[FAIL] Invalid CoT screening result")
            return False
    except Exception as e:
        print(f"[FAIL] CoT screening failed: {e}")
        return False


def test_review_agent(project_id: int):
    """Test review agent with Azure agent."""
    print("\n" + "="*60)
    print("TEST 8: Review Agent with Azure Agent")
    print("="*60)

    try:
        agent = ReviewAgent()

        paper = {
            "title": "Empagliflozin and Cardiovascular Outcomes in Patients with Type 2 Diabetes",
            "abstract": "This randomized trial evaluated empagliflozin in 7020 patients with type 2 diabetes. Empagliflozin reduced cardiovascular death by 38% and hospitalization for heart failure by 35%."
        }

        result = agent.review_paper(paper, pico_context="Population: Adults with T2DM | Intervention: SGLT2i")
        print(f"Population: {result.get('population')}")
        print(f"Intervention: {result.get('intervention')}")
        print(f"Main Findings: {result.get('main_findings')[:100]}...")

        if result.get('population') and result.get('intervention'):
            print("[OK] Review agent completed successfully")
            return True
        else:
            print("[FAIL] Review agent returned incomplete data")
            return False
    except Exception as e:
        print(f"[FAIL] Review agent failed: {e}")
        return False


def test_screening_labels_save(project_id: int):
    """Test saving screening labels to database."""
    print("\n" + "="*60)
    print("TEST 9: Screening Labels Save")
    print("="*60)

    try:
        # First get papers from the database
        with connect() as con:
            cur = con.execute("SELECT id FROM papers WHERE project_id = ? LIMIT 2", (project_id,))
            papers = cur.fetchall()

        if not papers:
            print("[SKIP] No papers in database to label")
            return True

        # Create labels
        labels = {papers[0][0]: "INCLUDE"}
        if len(papers) > 1:
            labels[papers[1][0]] = "EXCLUDE"

        with connect() as con:
            result = save_screening_labels(con, project_id, labels)
            con.commit()

        print(f"Saved: {result.get('saved')} labels")
        print(f"Updated: {result.get('updated_papers')} paper statuses")

        with connect() as con:
            stats = get_screening_stats(con, project_id)

        print(f"Screening Stats: {stats}")
        print("[OK] Screening labels saved successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Screening labels save failed: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("AI4SR Database Integration Test Suite")
    print("="*60)

    results = []

    # Test 1: DB Init
    success = test_db_init()
    results.append(("Database Init", success))
    if not success:
        print("\n[CRITICAL] Database initialization failed. Cannot continue.")
        return False

    # Test 2: Project Creation
    project_id = test_project_creation()
    results.append(("Project Creation", project_id is not None))
    if not project_id:
        print("\n[CRITICAL] Project creation failed. Cannot continue.")
        return False

    # Test 3: PICO Save/Retrieve
    success = test_pico_save_and_retrieve(project_id)
    results.append(("PICO Save/Retrieve", success))

    # Test 4: PICO Expansion
    success = test_pico_expansion(project_id)
    results.append(("PICO Expansion", success))

    # Test 5: Paper Insertion
    success = test_paper_insertion(project_id)
    results.append(("Paper Insertion", success))

    # Test 6: Screening
    success = test_screening(project_id)
    results.append(("Screening", success))

    # Test 7: CoT Screening
    success = test_cot_screening(project_id)
    results.append(("CoT Screening", success))

    # Test 8: Review Agent
    success = test_review_agent(project_id)
    results.append(("Review Agent", success))

    # Test 9: Screening Labels Save
    success = test_screening_labels_save(project_id)
    results.append(("Screening Labels Save", success))

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
