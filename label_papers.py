#!/usr/bin/env python3
"""
Interactive script for labeling papers for active learning screening.
Shows papers one by one and allows labeling as INCLUDE/EXCLUDE.
"""
import sys
import argparse
from datetime import datetime
from typing import Optional
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


def print_paper(paper: dict, index: int, total: int):
    """Print a paper for review."""
    print("\n" + "=" * 80)
    print(f"Paper {index}/{total}")
    print("=" * 80)
    print(f"\nID: {paper['id']}")
    print(f"\nTITLE: {paper.get('title', 'No title')}")
    print(f"\nABSTRACT:\n{paper.get('abstract', 'No abstract available')}")
    
    if paper.get('predicted_probability') is not None:
        prob = paper['predicted_probability']
        decision = "INCLUDE" if prob > 0.5 else "EXCLUDE"
        confidence = abs(prob - 0.5) * 2
        print(f"\n[MODEL PREDICTION: {decision} (P={prob:.3f}, confidence={confidence:.1%})]")
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


def label_papers_interactive(
    project_id: int,
    batch_size: int = 10,
    strategy: str = "relevance",
    classifier_type: str = "random_forest"
):
    """Interactive labeling session."""
    log(f"Starting labeling session for project_id={project_id}")
    log(f"Strategy: {strategy}, Classifier: {classifier_type}, Batch size: {batch_size}")
    
    labels_to_save = {}
    total_labeled = 0
    skipped = 0
    
    try:
        while True:
            # Get next batch
            log(f"\nFetching next batch of {batch_size} papers...")
            papers = get_next_batch(
                project_id, 
                batch_size=batch_size,
                strategy=strategy,
                classifier_type=classifier_type
            )
            
            if not papers:
                log("No more papers to label!")
                break
            
            log(f"Found {len(papers)} papers to review\n")
            
            # Label each paper
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
                    log(f"Labeled as {label} (total: {total_labeled})")
                else:
                    skipped += 1
                    log(f"Skipped (total skipped: {skipped})")
            
            # Save labels after batch
            if labels_to_save:
                log(f"\nSaving {len(labels_to_save)} labels...")
                with connect() as con:
                    result = save_screening_labels(con, project_id, labels_to_save)
                    con.commit()
                clear_model_cache(project_id)
                log(f"✓ Saved {result['saved']} labels, updated {result['updated_papers']} papers")
                labels_to_save = {}
                
                # Ask if continue
                continue_labeling = input("\nContinue with next batch? [Y/n]: ").strip().upper()
                if continue_labeling == 'N':
                    break
            else:
                log("\nNo labels to save from this batch")
                continue_labeling = input("Continue with next batch? [Y/n]: ").strip().upper()
                if continue_labeling == 'N':
                    break
        
        log(f"\n✓ Labeling session complete! Total labeled: {total_labeled}, Skipped: {skipped}")
        
    except KeyboardInterrupt:
        log("\n\nInterrupted by user")
        if labels_to_save:
            save = input(f"Save {len(labels_to_save)} unsaved labels? [y/N]: ").strip().upper()
            if save == 'Y':
                with connect() as con:
                    result = save_screening_labels(con, project_id, labels_to_save)
                    con.commit()
                clear_model_cache(project_id)
                log(f"Saved {result['saved']} labels")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive paper labeling for active learning screening"
    )
    parser.add_argument(
        "project_id",
        type=int,
        help="Project ID to label papers for"
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
    
    label_papers_interactive(
        args.project_id,
        batch_size=args.batch_size,
        strategy=args.strategy,
        classifier_type=args.classifier
    )


if __name__ == "__main__":
    main()

