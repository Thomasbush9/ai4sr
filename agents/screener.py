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
from db.repository import get_labeled_papers, get_unlabeled_papers


# Model cache per project_id
_model_cache: Dict[int, Optional[Pipeline]] = {}
_tfidf_cache: Dict[int, Optional[TfidfVectorizer]] = {}
COLD_START_THRESHOLD = 10  # Minimum labeled papers before active learning

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

