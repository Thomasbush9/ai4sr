#!/usr/bin/env python3
"""
CLI test script for active learning screening system.
Tests the full screening workflow: fetch batch, label, verify changes.
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from db.connection import connect
from db.repository import save_screening_labels
from agents.screener import get_next_batch, clear_model_cache


def log(message: str):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def print_papers(papers: list, title: str = "Papers"):
    """Print papers with titles and predicted probabilities."""
    log(f"\n{title} ({len(papers)} papers):")
    print("-" * 80)
    
    for i, paper in enumerate(papers, 1):
        prob = paper.get("predicted_probability")
        prob_str = f"{prob:.3f}" if prob is not None else "N/A (cold start)"
        title_text = paper.get("title", "No title")[:60]
        print(f"{i}. [{prob_str}] {title_text}...")
    print()


def test_screening(project_id: int, batch_size: int = 5):
    """Test the screening workflow."""
    log(f"Starting screening test for project_id={project_id}")
    
    try:
        # Step 1: Fetch first batch
        log("Step 1: Fetching first batch (relevance strategy)...")
        batch1 = get_next_batch(project_id, batch_size=batch_size, strategy="relevance")
        
        if not batch1:
            log("ERROR: No papers found. Make sure the project has papers in the database.")
            return
        
        print_papers(batch1, "First Batch (Before Labeling)")
        
        # Step 2: Submit dummy labels (mix of INCLUDE/EXCLUDE)
        log(f"Step 2: Submitting {len(batch1)} dummy labels...")
        
        labels = {}
        for i, paper in enumerate(batch1):
            # Alternate between INCLUDE and EXCLUDE
            label = "INCLUDE" if i % 2 == 0 else "EXCLUDE"
            labels[paper["id"]] = label
            log(f"  Paper {paper['id']}: {label}")
        
        with connect() as con:
            result = save_screening_labels(con, project_id, labels)
            con.commit()
        
        log(f"Saved {result['saved']} labels, updated {result['updated_papers']} papers")
        
        # Clear model cache to force retraining
        clear_model_cache(project_id)
        
        # Step 3: Fetch next batch again to verify changes
        log("Step 3: Fetching second batch (uncertainty strategy)...")
        batch2 = get_next_batch(project_id, batch_size=batch_size, strategy="uncertainty")
        
        if not batch2:
            log("No more unlabeled papers available.")
            return
        
        print_papers(batch2, "Second Batch (After Labeling)")
        
        # Verify that batch2 doesn't contain papers from batch1
        batch1_ids = {p["id"] for p in batch1}
        batch2_ids = {p["id"] for p in batch2}
        overlap = batch1_ids & batch2_ids
        
        if overlap:
            log(f"WARNING: Found {len(overlap)} papers in both batches (should be 0)")
        else:
            log("✓ Verified: No overlap between batches (correct)")
        
        # Step 4: Check statistics
        log("Step 4: Checking statistics...")
        with connect() as con:
            from db.repository import get_labeled_papers, get_unlabeled_papers
            
            labeled = get_labeled_papers(con, project_id)
            unlabeled = get_unlabeled_papers(con, project_id, limit=1000)
            
            log(f"Labeled papers: {len(labeled)}")
            log(f"Unlabeled papers: {len(unlabeled)}")
            
            if labeled:
                includes = sum(1 for p in labeled if p.get("label") == "INCLUDE")
                excludes = sum(1 for p in labeled if p.get("label") == "EXCLUDE")
                log(f"  INCLUDE: {includes}, EXCLUDE: {excludes}")
        
        log("✓ Test completed successfully!")
        
    except Exception as e:
        log(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Test the active learning screening system"
    )
    parser.add_argument(
        "project_id",
        type=int,
        help="Project ID to test screening for"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Batch size for testing (default: 5)"
    )
    
    args = parser.parse_args()
    
    test_screening(args.project_id, batch_size=args.batch_size)


if __name__ == "__main__":
    main()

