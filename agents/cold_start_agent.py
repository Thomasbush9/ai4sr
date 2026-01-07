"""
Cold-start agent for labeling initial papers using DSPY.
Labels the first ~10 papers to seed the active learning process.
"""
import dspy
from typing import Dict, List, Optional, Literal
from db.connection import connect
from db.repository import get_pico, get_unlabeled_papers, save_screening_labels
from agents.pico import pico_to_description, configure_dspy_safely


class ColdStartScreeningSig(dspy.Signature):
    """Screen a paper for systematic review inclusion based on PICO criteria.
    
    Given the PICO framework description and a paper's title and abstract,
    determine if the paper should be included in the systematic review.
    """
    pico_description: str = dspy.InputField(
        desc="PICO framework description: Population, Intervention, Comparison, Outcomes, Study design"
    )
    title: str = dspy.InputField(desc="Paper title")
    abstract: str = dspy.InputField(desc="Paper abstract")
    
    decision: Literal["INCLUDE", "EXCLUDE"] = dspy.OutputField(
        desc="Decision: INCLUDE if paper matches PICO criteria, EXCLUDE otherwise"
    )
    rationale: str = dspy.OutputField(
        desc="Brief explanation of the decision based on PICO criteria"
    )


class ColdStartAgent(dspy.Module):
    """DSPY module for cold-start paper screening."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        # Use ChainOfThought for better reasoning
        self.predict = dspy.ChainOfThought(ColdStartScreeningSig)
        
        # Configure DSPy if API key provided
        if api_key:
            configure_dspy_safely(api_key)
    
    def forward(self, pico_description: str, title: str, abstract: str) -> Dict[str, str]:
        """Screen a paper and return decision and rationale."""
        result = self.predict(
            pico_description=pico_description,
            title=title or "",
            abstract=abstract or ""
        )
        
        # Normalize decision to uppercase
        decision = result.decision.upper().strip()
        if decision not in ("INCLUDE", "EXCLUDE"):
            # Default to EXCLUDE if invalid
            decision = "EXCLUDE"
        
        return {
            "decision": decision,
            "rationale": result.rationale or ""
        }


def run_cold_start(project_id: int, n: int = 10, api_key: Optional[str] = None) -> Dict:
    """
    Run cold-start agent to label initial papers.
    
    Args:
        project_id: Project ID
        n: Number of papers to label (default 10)
        api_key: Optional OpenAI API key
    
    Returns:
        Dict with:
            - n_labeled_by_agent: Number of papers labeled
            - included_count: Number of INCLUDE labels
            - excluded_count: Number of EXCLUDE labels
            - results: List of dicts with paper_id, label, rationale
    """
    # Configure DSPy
    if api_key:
        configure_dspy_safely(api_key)
    else:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("OPENAI_KEY")
        if api_key:
            configure_dspy_safely(api_key)
    
    with connect() as con:
        # Fetch PICO
        pico = get_pico(con, project_id)
        if not pico:
            raise ValueError(f"No PICO found for project {project_id}. Please create PICO first.")
        
        # Convert PICO to description
        pico_description = pico_to_description(pico)
        
        # Fetch n UNSCREENED papers
        unlabeled = get_unlabeled_papers(con, project_id, limit=n)
        if not unlabeled:
            return {
                "n_labeled_by_agent": 0,
                "included_count": 0,
                "excluded_count": 0,
                "results": []
            }
        
        # Initialize agent
        agent = ColdStartAgent(api_key=api_key)
        
        # Label each paper
        labels_to_save = {}
        results = []
        included_count = 0
        excluded_count = 0
        
        for paper in unlabeled:
            paper_id = paper["paper_id"]
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            
            # Skip if no title/abstract
            if not title and not abstract:
                continue
            
            # Get decision from agent
            try:
                result = agent.forward(
                    pico_description=pico_description,
                    title=title,
                    abstract=abstract
                )
                
                label = result["decision"]
                rationale = result.get("rationale", "")
                
                # Store label
                labels_to_save[paper_id] = label
                
                # Track counts
                if label == "INCLUDE":
                    included_count += 1
                else:
                    excluded_count += 1
                
                # Store result
                results.append({
                    "paper_id": paper_id,
                    "label": label,
                    "rationale": rationale,
                    "title": title
                })
                
            except Exception as e:
                # Skip paper on error, continue with others
                print(f"Warning: Failed to label paper {paper_id}: {e}")
                continue
        
        # Save labels (using default source='manual' for now, can be updated later)
        if labels_to_save:
            save_screening_labels(con, project_id, labels_to_save)
            con.commit()
        
        return {
            "n_labeled_by_agent": len(labels_to_save),
            "included_count": included_count,
            "excluded_count": excluded_count,
            "results": results
        }


