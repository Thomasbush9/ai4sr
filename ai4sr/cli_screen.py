#!/usr/bin/env python3
"""
Interactive CLI tool for paper screening with active learning.
Provides a terminal-based interface for labeling papers and testing the screening workflow.
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import internal functions for direct API access
from db.connection import connect
from db.repository import get_screening_stats
from agents.screener import get_next_batch, should_stop_screening
from db.repository import save_screening_labels
from agents.screener import clear_model_cache


def log(message: str):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def print_status(project_id: int):
    """Print current screening status."""
    with connect() as con:
        stats = get_screening_stats(con, project_id)
    
    log("=" * 80)
    log(f"Screening Status for Project {project_id}")
    log("=" * 80)
    print(f"\nTotal Papers:     {stats['n_total_corpus']}")
    print(f"Labeled:          {stats['n_labeled']}")
    print(f"Unlabeled:        {stats['n_unlabeled']}")
    print(f"Included:         {stats['n_included']}")
    print(f"Excluded:         {stats['n_excluded']}")
    
    if stats.get('last_batch_timestamp'):
        print(f"\nLast Batch:       {stats['last_batch_timestamp']}")
    
    progress = (stats['n_labeled'] / stats['n_total_corpus'] * 100) if stats['n_total_corpus'] > 0 else 0
    print(f"Progress:         {progress:.1f}%")
    print()


def print_paper(paper: dict, index: int, total: int):
    """Print a paper for review."""
    print("\n" + "-" * 80)
    print(f"Paper {index}/{total}")
    print("-" * 80)
    print(f"\nID: {paper['id']}")
    print(f"\nTitle: {paper.get('title', 'No title')}")
    
    if paper.get('venue') or paper.get('year'):
        venue_year = []
        if paper.get('venue'):
            venue_year.append(paper['venue'])
        if paper.get('year'):
            venue_year.append(f"({paper['year']})")
        print(f"Source: {' '.join(venue_year)}")
    
    if paper.get('predicted_probability') is not None:
        prob = paper['predicted_probability']
        decision = "INCLUDE" if prob > 0.5 else "EXCLUDE"
        confidence = abs(prob - 0.5) * 2
        print(f"\n[Predicted: {decision} (P={prob:.3f}, confidence={confidence:.1%})]")
    
    abstract = paper.get('abstract', 'No abstract available')
    if abstract:
        # Truncate long abstracts
        if len(abstract) > 500:
            abstract = abstract[:500] + "..."
        print(f"\nAbstract:\n{abstract}")
    print()


def get_label_from_user() -> Optional[str]:
    """Get label from user input."""
    while True:
        response = input("Label [I]nclude / [E]xclude / [S]kip / [Q]uit: ").strip().upper()
        if response in ('I', 'INCLUDE', '1'):
            return 'INCLUDE'
        elif response in ('E', 'EXCLUDE', '0'):
            return 'EXCLUDE'
        elif response in ('S', 'SKIP'):
            return None
        elif response in ('Q', 'QUIT'):
            return 'QUIT'
        else:
            print("Invalid input. Please enter I (Include), E (Exclude), S (Skip), or Q (Quit)")


def screen_interactive(project_id: int, batch_size: int = 10, strategy: str = "relevance", classifier_type: str = "random_forest"):
    """Interactive screening session."""
    log(f"Starting interactive screening for project_id={project_id}")
    log(f"Strategy: {strategy}, Classifier: {classifier_type}, Batch size: {batch_size}")
    
    total_labeled = 0
    batch_num = 0
    
    try:
        while True:
            batch_num += 1
            log(f"\n{'='*80}")
            log(f"Batch {batch_num}")
            log(f"{'='*80}\n")
            
            # Print status
            print_status(project_id)
            
            # Check if should stop
            if should_stop_screening(project_id):
                log("✓ Screening complete! Stopping rules triggered.")
                with connect() as con:
                    stats = get_screening_stats(con, project_id)
                print(f"\nFinal Results:")
                print(f"  Total Papers: {stats['n_total_corpus']}")
                print(f"  Labeled: {stats['n_labeled']}")
                print(f"  Included: {stats['n_included']}")
                print(f"  Excluded: {stats['n_excluded']}")
                break
            
            # Get next batch
            log("Fetching next batch...")
            papers = get_next_batch(
                project_id,
                batch_size=batch_size,
                strategy=strategy,
                classifier_type=classifier_type
            )
            
            if not papers:
                log("No more papers to screen!")
                break
            
            log(f"Received {len(papers)} papers to review\n")
            
            # Label each paper
            labels_to_save = {}
            for i, paper in enumerate(papers, 1):
                print_paper(paper, i, len(papers))
                
                label = get_label_from_user()
                
                if label == 'QUIT':
                    if labels_to_save:
                        save = input(f"\nSave {len(labels_to_save)} labels before quitting? [y/N]: ").strip().upper()
                        if save == 'Y':
                            with connect() as con:
                                result = save_screening_labels(con, project_id, labels_to_save)
                                con.commit()
                            clear_model_cache(project_id)
                            log(f"Saved {result['saved']} labels")
                    log("Quitting...")
                    return
                elif label:
                    labels_to_save[paper['id']] = label
                    total_labeled += 1
            
            # Save labels
            if labels_to_save:
                log(f"\nSaving {len(labels_to_save)} labels...")
                with connect() as con:
                    result = save_screening_labels(con, project_id, labels_to_save)
                    con.commit()
                clear_model_cache(project_id)
                log(f"✓ Saved {result['saved']} labels, updated {result['updated_papers']} papers")
            
            # Ask if continue
            continue_labeling = input("\nContinue with next batch? [Y/n]: ").strip().upper()
            if continue_labeling == 'N':
                break
        
        log(f"\n✓ Screening session complete! Total labeled in this session: {total_labeled}")
        
    except KeyboardInterrupt:
        log("\n\nInterrupted by user")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive CLI tool for paper screening with active learning"
    )
    parser.add_argument(
        "project_id",
        type=int,
        help="Project ID to screen papers for"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of papers per batch (default: 10)"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="relevance",
        choices=["relevance", "uncertainty"],
        help="Active learning strategy (default: relevance)"
    )
    parser.add_argument(
        "--classifier",
        type=str,
        default="random_forest",
        choices=["logistic", "svm", "random_forest", "naive_bayes"],
        help="Classifier type (default: random_forest)"
    )
    
    args = parser.parse_args()
    
    screen_interactive(
        args.project_id,
        batch_size=args.batch_size,
        strategy=args.strategy,
        classifier_type=args.classifier
    )


if __name__ == "__main__":
    main()

