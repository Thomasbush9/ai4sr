"""
Agent for reviewing included papers and extracting structured summaries using DSPy.
"""
import dspy
from typing import Dict, List, Optional, Any
import json
from db.connection import connect
from db.repository import get_included_papers, save_agent_summary, save_project_overview
from agents.pico import configure_dspy_safely


class PaperReviewSignature(dspy.Signature):
    """Extract structured information from a research paper."""
    
    title: str = dspy.InputField(desc="Paper title")
    abstract: str = dspy.InputField(desc="Paper abstract")
    pico_context: str = dspy.InputField(desc="Optional PICO context for the review")
    
    population: str = dspy.OutputField(desc="Population studied (patients, participants, etc.)")
    intervention: str = dspy.OutputField(desc="Intervention or treatment being studied")
    comparator: str = dspy.OutputField(desc="Comparison or control group")
    outcomes: str = dspy.OutputField(desc="Outcomes measured")
    main_findings: str = dspy.OutputField(desc="Main findings or conclusions")
    sample_size: str = dspy.OutputField(desc="Sample size or number of participants")


class OverviewSignature(dspy.Signature):
    """Generate a comprehensive overview synthesizing multiple paper summaries."""
    
    summaries: str = dspy.InputField(desc="Structured summaries from multiple papers")
    pico_context: str = dspy.InputField(desc="PICO context for the review")
    
    overview: str = dspy.OutputField(desc="Comprehensive overview synthesizing the findings")


class ReviewAgent(dspy.Module):
    """Agent that reviews papers and extracts structured summaries."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        
        # Configure DSPy if API key provided
        if self.api_key and self.api_key != "your_openai_api_key_here":
            configure_dspy_safely(self.api_key)
        
        # Initialize predictor for paper review
        self.paper_reviewer = dspy.Predict(PaperReviewSignature)
        
        # Initialize predictor for overview generation
        self.overview_generator = dspy.Predict(OverviewSignature)
    
    def review_paper(self, paper: Dict, pico_context: Optional[str] = None) -> Dict:
        """
        Review a single paper and extract structured information.
        
        Args:
            paper: Dict with paper data (title, abstract, etc.)
            pico_context: Optional PICO context string
        
        Returns:
            Dict with extracted fields: population, intervention, comparator, outcomes, main_findings, sample_size
        """
        title = paper.get("title", "")
        abstract = paper.get("abstract", "") or ""
        
        # Prepare PICO context
        pico_str = pico_context or "No specific PICO context provided."
        
        # Extract structured information
        result = self.paper_reviewer(
            title=title,
            abstract=abstract,
            pico_context=pico_str
        )
        
        return {
            "population": result.population or "",
            "intervention": result.intervention or "",
            "comparator": result.comparator or "",
            "outcomes": result.outcomes or "",
            "main_findings": result.main_findings or "",
            "sample_size": result.sample_size or ""
        }
    
    def generate_overview(self, summaries: List[Dict], pico_context: Optional[str] = None) -> str:
        """
        Generate a comprehensive overview from multiple paper summaries.
        
        Args:
            summaries: List of summary dicts
            pico_context: Optional PICO context string
        
        Returns:
            Overview text
        """
        # Format summaries for input
        summaries_text = "\n\n".join([
            f"Paper {i+1}:\n"
            f"Population: {s.get('population', 'N/A')}\n"
            f"Intervention: {s.get('intervention', 'N/A')}\n"
            f"Comparator: {s.get('comparator', 'N/A')}\n"
            f"Outcomes: {s.get('outcomes', 'N/A')}\n"
            f"Main Findings: {s.get('main_findings', 'N/A')}\n"
            f"Sample Size: {s.get('sample_size', 'N/A')}"
            for i, s in enumerate(summaries)
        ])
        
        pico_str = pico_context or "No specific PICO context provided."
        
        result = self.overview_generator(
            summaries=summaries_text,
            pico_context=pico_str
        )
        
        return result.overview or ""


def review_included_papers(
    project_id: int,
    pico: Optional[Dict] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Review all included papers for a project and generate summaries.
    
    Args:
        project_id: Project ID
        pico: Optional PICO dict for context
        api_key: Optional API key for LLM
    
    Returns:
        Dict with counts and status
    """
    # Get included papers
    with connect() as con:
        included_papers = get_included_papers(con, project_id)
    
    if not included_papers:
        return {
            "n_included": 0,
            "n_summarized": 0,
            "overview_generated": False,
            "error": "No included papers found for this project"
        }
    
    # Prepare PICO context
    pico_context = None
    if pico:
        parts = []
        if pico.get("population"):
            parts.append(f"Population: {pico['population']}")
        if pico.get("intervention"):
            parts.append(f"Intervention: {pico['intervention']}")
        if pico.get("comparison"):
            parts.append(f"Comparison: {pico['comparison']}")
        if pico.get("outcome"):
            parts.append(f"Outcome: {pico['outcome']}")
        if parts:
            pico_context = " | ".join(parts)
    
    # Initialize review agent
    agent = ReviewAgent(api_key=api_key)
    
    # Review each paper
    summaries = []
    summarized_count = 0
    
    for paper in included_papers:
        try:
            # Extract structured information
            summary_data = agent.review_paper(paper, pico_context=pico_context)
            
            # Add notes field (empty for now)
            summary_data["notes"] = ""
            
            # Save summary to database
            with connect() as con:
                save_agent_summary(con, project_id, paper["paper_id"], summary_data)
                con.commit()
            
            summaries.append(summary_data)
            summarized_count += 1
            
        except Exception as e:
            print(f"Error reviewing paper {paper.get('paper_id')}: {e}")
            continue
    
    # Generate overview if we have summaries
    overview_generated = False
    if summaries:
        try:
            overview_text = agent.generate_overview(summaries, pico_context=pico_context)
            
            # Create overview JSON structure
            overview_json = {
                "project_id": project_id,
                "summary_count": len(summaries),
                "overview": overview_text,
                "pico_context": pico_context
            }
            
            # Save overview
            with connect() as con:
                save_project_overview(con, project_id, overview_json)
                con.commit()
            
            overview_generated = True
            
        except Exception as e:
            print(f"Error generating overview: {e}")
    
    return {
        "n_included": len(included_papers),
        "n_summarized": summarized_count,
        "overview_generated": overview_generated
    }

