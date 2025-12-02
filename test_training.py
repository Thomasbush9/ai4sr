#!/usr/bin/env python3
"""
Dry-run test script for ML model training.
Trains the model and shows predictions without saving anything to the database.
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from db.connection import connect
from db.repository import get_labeled_papers, get_unlabeled_papers
from agents.screener import _train_model, _predict_probabilities, _build_text_features, DEFAULT_CLASSIFIER


def log(message: str):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def print_labeled_stats(labeled_papers: list):
    """Print statistics about labeled papers."""
    includes = sum(1 for p in labeled_papers if p.get("label") == "INCLUDE")
    excludes = sum(1 for p in labeled_papers if p.get("label") == "EXCLUDE")
    
    log(f"Labeled papers: {len(labeled_papers)} total")
    log(f"  INCLUDE: {includes}")
    log(f"  EXCLUDE: {excludes}")
    log(f"  Ratio: {includes/(includes+excludes)*100:.1f}% INCLUDE" if (includes+excludes) > 0 else "  Ratio: N/A")


def print_predictions(papers: list, probabilities: list, top_n: int = 10):
    """Print predictions with probabilities."""
    # Combine papers with probabilities
    papers_with_probs = [
        {
            "paper": p,
            "prob": prob
        }
        for p, prob in zip(papers, probabilities)
    ]
    
    # Sort by probability descending
    papers_with_probs.sort(key=lambda x: x["prob"], reverse=True)
    
    log(f"\nTop {min(top_n, len(papers_with_probs))} Predictions (highest P(INCLUDE)):")
    print("-" * 100)
    
    for i, item in enumerate(papers_with_probs[:top_n], 1):
        paper = item["paper"]
        prob = item["prob"]
        title = (paper.get("title", "No title") or "No title")[:70]
        decision = "INCLUDE" if prob > 0.5 else "EXCLUDE"
        confidence = abs(prob - 0.5) * 2  # Convert to 0-1 scale
        
        print(f"{i:3d}. [{prob:.3f}] {decision:8s} (confidence: {confidence:.1%}) - {title}...")
    
    print()
    
    # Also show uncertainty ranking
    papers_with_probs_uncertain = sorted(papers_with_probs, key=lambda x: abs(x["prob"] - 0.5))
    
    log(f"\nTop {min(top_n, len(papers_with_probs_uncertain))} Uncertain Predictions (closest to 0.5):")
    print("-" * 100)
    
    for i, item in enumerate(papers_with_probs_uncertain[:top_n], 1):
        paper = item["paper"]
        prob = item["prob"]
        title = (paper.get("title", "No title") or "No title")[:70]
        uncertainty = abs(prob - 0.5)
        
        print(f"{i:3d}. [{prob:.3f}] (uncertainty: {uncertainty:.3f}) - {title}...")


def test_training(project_id: int, num_predictions: int = 20, classifier_type: str = DEFAULT_CLASSIFIER):
    """Test the ML model training and prediction without saving anything."""
    log(f"Starting training test for project_id={project_id} (DRY RUN - no changes will be saved)")
    log(f"Classifier: {classifier_type}")
    
    try:
        with connect() as con:
            # Step 1: Get labeled papers
            log("Step 1: Loading labeled papers...")
            labeled = get_labeled_papers(con, project_id)
            
            if not labeled:
                log("ERROR: No labeled papers found. Please label some papers first using label_papers.py")
                return
            
            print_labeled_stats(labeled)
            
            if len(labeled) < 2:
                log("ERROR: Need at least 2 labeled papers to train the model")
                return
            
            # Check if we have both classes
            labels = [p.get("label") for p in labeled]
            if "INCLUDE" not in labels or "EXCLUDE" not in labels:
                log("WARNING: Need at least one INCLUDE and one EXCLUDE label for training")
                log("Model will be trained but may not work well with only one class")
            
            # Step 2: Train the model
            log(f"\nStep 2: Training TF-IDF + {classifier_type} model...")
            model = _train_model(labeled, classifier_type=classifier_type)
            
            if model is None:
                log("ERROR: Model training failed. Check your labeled data.")
                return
            
            log("✓ Model trained successfully!")
            
            # Get model info
            clf = model.named_steps['clf']
            # Handle CalibratedClassifierCV wrapper
            actual_clf = clf.base_estimator if hasattr(clf, 'base_estimator') else clf
            log(f"  Model type: {type(actual_clf).__name__}")
            log(f"  Number of features: {len(model.named_steps['tfidf'].vocabulary_)}")
            log(f"  Number of training samples: {len(labeled)}")
            
            # Step 3: Get unlabeled papers for prediction
            log("\nStep 3: Loading unlabeled papers for prediction...")
            unlabeled = get_unlabeled_papers(con, project_id, limit=num_predictions * 2)
            
            if not unlabeled:
                log("No unlabeled papers found.")
                return
            
            log(f"Found {len(unlabeled)} unlabeled papers")
            
            # Step 4: Make predictions
            log(f"\nStep 4: Making predictions on {min(len(unlabeled), num_predictions)} papers...")
            papers_to_predict = unlabeled[:num_predictions]
            probabilities = _predict_probabilities(model, papers_to_predict)
            
            # Step 5: Show results
            print_predictions(papers_to_predict, probabilities, top_n=num_predictions)
            
            # Step 6: Model statistics
            log("\nStep 5: Model Statistics:")
            probs_array = probabilities
            avg_prob = sum(probs_array) / len(probs_array)
            high_confidence_includes = sum(1 for p in probs_array if p > 0.7)
            high_confidence_excludes = sum(1 for p in probs_array if p < 0.3)
            uncertain = sum(1 for p in probs_array if 0.4 <= p <= 0.6)
            
            log(f"  Average P(INCLUDE): {avg_prob:.3f}")
            log(f"  High confidence INCLUDE (P>0.7): {high_confidence_includes}")
            log(f"  High confidence EXCLUDE (P<0.3): {high_confidence_excludes}")
            log(f"  Uncertain predictions (0.4≤P≤0.6): {uncertain}")
            
            log("\n✓ Training test completed successfully! (No data was saved)")


    except Exception as e:
        log(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Test ML model training (dry-run, no data saved)"
    )
    parser.add_argument(
        "project_id",
        type=int,
        help="Project ID to test training for"
    )
    parser.add_argument(
        "--num-predictions",
        type=int,
        default=20,
        help="Number of papers to make predictions on (default: 20)"
    )
    parser.add_argument(
        "--classifier",
        type=str,
        default=DEFAULT_CLASSIFIER,
        choices=["logistic", "svm", "random_forest", "naive_bayes"],
        help=f"Classifier type (default: {DEFAULT_CLASSIFIER})"
    )
    
    args = parser.parse_args()
    
    test_training(args.project_id, num_predictions=args.num_predictions, classifier_type=args.classifier)


if __name__ == "__main__":
    main()

