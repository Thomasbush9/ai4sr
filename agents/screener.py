"""
Active learning screener for paper screening using TF-IDF and multiple classifiers.
Implements cold start (random sampling) and active learning strategies (relevance, uncertainty).
Supports: LogisticRegression, SVM, RandomForest, NaiveBayes
"""
import random
from typing import Dict, List, Optional, Literal
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from db.connection import connect
from db.repository import get_labeled_papers, get_unlabeled_papers, get_screening_stats, get_recent_batch_statistics


# Model cache per project_id
_model_cache: Dict[int, Optional[Pipeline]] = {}
_tfidf_cache: Dict[int, Optional[TfidfVectorizer]] = {}
COLD_START_THRESHOLD = 10  # Minimum labeled papers before active learning

# Stopping rule thresholds
MIN_UNLABELED_THRESHOLD = 50  # Rule A: stop when fewer than N unlabeled papers remain
LOW_YIELD_BATCH_COUNT = 5  # Rule B: check last N batches
LOW_YIELD_BATCH_SIZE = 20  # Rule B: assume batch size for calculations
LOW_YIELD_RATE_THRESHOLD = 0.02  # Rule B: stop if include rate < 2%

# Classifier readiness thresholds
MIN_SEED_LABELS = 100  # Minimum total labeled papers for auto-labeling
MIN_POSITIVE_LABELS = 20  # Minimum INCLUDE labels
MIN_NEGATIVE_LABELS = 20  # Minimum EXCLUDE labels

# Auto-labeling thresholds
INCLUDE_THRESHOLD = 0.8  # P(INCLUDE) >= 0.8 to auto-label as INCLUDE
EXCLUDE_THRESHOLD = 0.2  # P(INCLUDE) <= 0.2 to auto-label as EXCLUDE

# Default classifier type
DEFAULT_CLASSIFIER = "random_forest"  # Options: "logistic", "svm", "random_forest", "naive_bayes"


def _build_text_features(title: str, abstract: str) -> str:
    """Combine title and abstract for feature extraction."""
    title = title or ""
    abstract = abstract or ""
    return f"{title} {abstract}".strip()


def _create_classifier(classifier_type: str):
    """
    Create a classifier based on type.
    
    Args:
        classifier_type: "logistic", "svm", "random_forest", "naive_bayes"
    
    Returns:
        Classifier instance
    """
    if classifier_type == "logistic":
        return LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    elif classifier_type == "svm":
        # SVM needs calibration for probability estimates
        base_svm = SVC(class_weight='balanced', random_state=42, probability=True, kernel='linear')
        return CalibratedClassifierCV(base_svm, cv=3)
    elif classifier_type == "random_forest":
        return RandomForestClassifier(
            class_weight='balanced', 
            random_state=42, 
            n_estimators=100,
            max_depth=10,
            min_samples_split=2
        )
    elif classifier_type == "naive_bayes":
        return MultinomialNB(alpha=1.0)
    else:
        raise ValueError(f"Unknown classifier type: {classifier_type}")


def _train_model(labeled_papers: List[Dict], classifier_type: str = DEFAULT_CLASSIFIER) -> Optional[Pipeline]:
    """
    Train a TF-IDF + classifier model on labeled papers.
    
    Args:
        labeled_papers: List of dicts with keys: paper_id, title, abstract, label
        classifier_type: "logistic", "svm", "random_forest", "naive_bayes"
    
    Returns:
        Trained pipeline or None if insufficient data
    """
    if len(labeled_papers) < 2:
        return None
    
    # Prepare features and labels
    texts = []
    labels = []
    
    for paper in labeled_papers:
        text = _build_text_features(paper.get("title", ""), paper.get("abstract", ""))
        if not text.strip():
            continue
        texts.append(text)
        # Convert label to binary: INCLUDE=1, EXCLUDE=0
        label = 1 if paper.get("label") == "INCLUDE" else 0
        labels.append(label)
    
    if len(texts) < 2 or len(set(labels)) < 2:
        # Need at least 2 samples and both classes
        return None
    
    # Adjust TF-IDF max_features based on dataset size
    max_features = min(5000, max(100, len(texts) * 10))
    
    # Build pipeline
    clf = _create_classifier(classifier_type)
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(max_features=max_features, stop_words='english', ngram_range=(1, 2))),
        ('clf', clf)
    ])
    
    try:
        pipeline.fit(texts, labels)
        return pipeline
    except Exception as e:
        print(f"Warning: Failed to train model ({classifier_type}): {e}")
        return None


def _get_cached_model(project_id: int) -> Optional[Pipeline]:
    """Get cached model for project, or None if not cached."""
    return _model_cache.get(project_id)


def _cache_model(project_id: int, model: Optional[Pipeline]):
    """Cache model for project."""
    _model_cache[project_id] = model


def _predict_probabilities(model: Pipeline, papers: List[Dict]) -> List[float]:
    """
    Predict probabilities for papers using the model.
    
    Returns:
        List of P(INCLUDE) probabilities
    """
    texts = [_build_text_features(p.get("title", ""), p.get("abstract", "")) for p in papers]
    
    try:
        # Get probability of positive class (INCLUDE)
        probs = model.predict_proba(texts)[:, 1]
        return probs.tolist()
    except Exception as e:
        print(f"Warning: Failed to predict probabilities: {e}")
        # Return neutral probabilities on error
        return [0.5] * len(papers)


def get_next_batch(
    project_id: int,
    batch_size: int = 10,
    strategy: Literal["relevance", "uncertainty"] = "relevance",
    classifier_type: str = DEFAULT_CLASSIFIER
) -> List[Dict]:
    """
    Get next batch of papers to label using active learning.
    
    Args:
        project_id: Project ID
        batch_size: Number of papers to return
        strategy: "relevance" (rank by P(INCLUDE)) or "uncertainty" (rank by |p-0.5|)
        classifier_type: "logistic", "svm", "random_forest", "naive_bayes"
    
    Returns:
        List of dicts with keys: id, title, abstract, predicted_probability
    """
    with connect() as con:
        # Check stopping rules first
        if should_stop_screening(project_id):
            return []  # Empty list signals completion (will be wrapped with done=true in API)
        
        # Get labeled papers to check if we have enough for active learning
        labeled = get_labeled_papers(con, project_id)
        
        # Cold start: random sampling if not enough labels
        if len(labeled) < COLD_START_THRESHOLD:
            unlabeled = get_unlabeled_papers(con, project_id, limit=batch_size * 10)
            if not unlabeled:
                return []
            
            # Random sample
            selected = random.sample(unlabeled, min(batch_size, len(unlabeled)))
            
            # Add predicted_probability as None for cold start
            return [
                {
                    "id": p["paper_id"],
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract", ""),
                    "venue": p.get("venue"),
                    "year": p.get("year"),
                    "predicted_probability": None
                }
                for p in selected
            ]
        
        # Active learning: train/use model
        model = _get_cached_model(project_id)
        
        # Retrain if model not cached or if we have new labels
        if model is None:
            model = _train_model(labeled, classifier_type=classifier_type)
            if model is None:
                # Fallback to random if training fails
                unlabeled = get_unlabeled_papers(con, project_id, limit=batch_size * 10)
                selected = random.sample(unlabeled, min(batch_size, len(unlabeled))) if unlabeled else []
                return [
                    {
                        "id": p["paper_id"],
                        "title": p.get("title", ""),
                        "abstract": p.get("abstract", ""),
                        "venue": p.get("venue"),
                        "year": p.get("year"),
                        "predicted_probability": None
                    }
                    for p in selected
                ]
            _cache_model(project_id, model)
        
        # Get unlabeled papers
        unlabeled = get_unlabeled_papers(con, project_id, limit=None)
        if not unlabeled:
            return []
        
        # Predict probabilities
        probs = _predict_probabilities(model, unlabeled)
        
        # Create list with probabilities
        papers_with_probs = [
            {
                "paper": p,
                "probability": prob
            }
            for p, prob in zip(unlabeled, probs)
        ]
        
        # Rank based on strategy
        if strategy == "relevance":
            # Rank by P(INCLUDE) descending (most likely to include first)
            papers_with_probs.sort(key=lambda x: x["probability"], reverse=True)
        elif strategy == "uncertainty":
            # Rank by |p - 0.5| ascending (least certain first)
            papers_with_probs.sort(key=lambda x: abs(x["probability"] - 0.5))
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Select top batch_size
        selected = papers_with_probs[:batch_size]
        
        return [
            {
                "id": s["paper"]["paper_id"],
                "title": s["paper"].get("title", ""),
                "abstract": s["paper"].get("abstract", ""),
                "venue": s["paper"].get("venue"),
                "year": s["paper"].get("year"),
                "predicted_probability": float(s["probability"])
            }
            for s in selected
        ]


def clear_model_cache(project_id: Optional[int] = None):
    """
    Clear model cache for a project or all projects.
    
    Args:
        project_id: Project ID to clear cache for, or None to clear all
    """
    if project_id is None:
        _model_cache.clear()
    else:
        _model_cache.pop(project_id, None)


def should_stop_screening(project_id: int) -> bool:
    """
    Check if screening should stop based on stopping rules.
    
    Rule A - Min Coverage: Stop when n_unlabeled < threshold (default: 50)
    Rule B - Low Yield: Stop if include rate in last K batches < threshold (default: 2%)
    
    Args:
        project_id: Project ID
    
    Returns:
        True if screening should stop, False otherwise
    """
    with connect() as con:
        # Get current statistics
        stats = get_screening_stats(con, project_id)
        n_unlabeled = stats.get("n_unlabeled", 0)
        
        # Rule A: Min Coverage
        if n_unlabeled < MIN_UNLABELED_THRESHOLD:
            return True
        
        # Rule B: Low Yield (only check if we have enough labels)
        if stats.get("n_labeled", 0) >= LOW_YIELD_BATCH_COUNT * LOW_YIELD_BATCH_SIZE:
            batch_stats = get_recent_batch_statistics(con, project_id, batch_count=LOW_YIELD_BATCH_COUNT)
            include_rate = batch_stats.get("include_rate", 1.0)
            
            if include_rate < LOW_YIELD_RATE_THRESHOLD:
                return True
        
        return False


def classifier_ready(project_id: int) -> bool:
    """
    Check if classifier is ready for auto-labeling (enough seed labels).
    
    Args:
        project_id: Project ID
    
    Returns:
        True if classifier is ready (enough labeled papers with balanced classes)
    """
    with connect() as con:
        labeled = get_labeled_papers(con, project_id)
        
        if len(labeled) < MIN_SEED_LABELS:
            return False
        
        # Count INCLUDE and EXCLUDE
        include_count = sum(1 for p in labeled if p.get("label") == "INCLUDE")
        exclude_count = sum(1 for p in labeled if p.get("label") == "EXCLUDE")
        
        # Check minimums for both classes
        if include_count < MIN_POSITIVE_LABELS:
            return False
        if exclude_count < MIN_NEGATIVE_LABELS:
            return False
        
        return True


def train_classifier(project_id: int, classifier_type: str = DEFAULT_CLASSIFIER) -> Optional[Pipeline]:
    """
    Train a classifier for a project. Reusable function that fetches labeled papers and trains model.
    
    Args:
        project_id: Project ID
        classifier_type: "logistic", "svm", "random_forest", "naive_bayes"
    
    Returns:
        Trained pipeline or None if training fails
    """
    with connect() as con:
        labeled = get_labeled_papers(con, project_id)
    
    if not labeled:
        return None
    
    # Check cache first
    cached_model = _get_cached_model(project_id)
    if cached_model is not None:
        return cached_model
    
    # Train model
    model = _train_model(labeled, classifier_type=classifier_type)
    
    # Cache the model
    if model is not None:
        _cache_model(project_id, model)
    
    return model


def auto_label_papers(
    project_id: int,
    classifier_type: str = DEFAULT_CLASSIFIER,
    include_threshold: float = INCLUDE_THRESHOLD,
    exclude_threshold: float = EXCLUDE_THRESHOLD
) -> Dict:
    """
    Auto-label remaining unscreened papers using trained classifier.
    
    Args:
        project_id: Project ID
        classifier_type: Classifier type to use
        include_threshold: Probability threshold for INCLUDE (default 0.8)
        exclude_threshold: Probability threshold for EXCLUDE (default 0.2)
    
    Returns:
        Dict with counts: auto_included, auto_excluded, borderline, still_unscreened
    """
    # Check classifier readiness
    if not classifier_ready(project_id):
        raise ValueError(
            f"Classifier not ready. Need at least {MIN_SEED_LABELS} labeled papers "
            f"with at least {MIN_POSITIVE_LABELS} INCLUDE and {MIN_NEGATIVE_LABELS} EXCLUDE."
        )
    
    # Train classifier
    model = train_classifier(project_id, classifier_type=classifier_type)
    if model is None:
        raise ValueError("Failed to train classifier. Check labeled data quality.")
    
    # Get all unscreened papers
    with connect() as con:
        # Query for papers with status UNSCREENED
        cur = con.execute("""
            SELECT p.id as paper_id, p.title, p.abstract
            FROM papers p
            LEFT JOIN screening_labels sl ON p.id = sl.paper_id AND sl.project_id = ?
            WHERE p.project_id = ? AND sl.id IS NULL AND p.status = 'UNSCREENED'
        """, (project_id, project_id))
        cols = [c[0] for c in cur.description]
        unscreened_papers = [dict(zip(cols, r)) for r in cur.fetchall()]
    
    if not unscreened_papers:
        return {
            "auto_included": 0,
            "auto_excluded": 0,
            "borderline": 0,
            "still_unscreened": 0
        }
    
    # Predict probabilities
    probs = _predict_probabilities(model, unscreened_papers)
    
    # Apply thresholds and collect labels
    labels_to_save = {}
    auto_included = 0
    auto_excluded = 0
    borderline = 0
    
    for paper, prob in zip(unscreened_papers, probs):
        if prob >= include_threshold:
            labels_to_save[paper["paper_id"]] = "INCLUDE"
            auto_included += 1
        elif prob <= exclude_threshold:
            labels_to_save[paper["paper_id"]] = "EXCLUDE"
            auto_excluded += 1
        else:
            # Borderline - leave as UNSCREENED
            borderline += 1
    
    # Save labels
    if labels_to_save:
        with connect() as con:
            from db.repository import save_screening_labels
            save_screening_labels(con, project_id, labels_to_save)
            con.commit()
        
        # Clear cache to force retraining with new labels
        clear_model_cache(project_id)
    
    still_unscreened = len(unscreened_papers) - auto_included - auto_excluded
    
    return {
        "auto_included": auto_included,
        "auto_excluded": auto_excluded,
        "borderline": borderline,
        "still_unscreened": still_unscreened
    }

