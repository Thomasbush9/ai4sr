"""
Agent for reviewing included papers and extracting structured summaries using Azure OpenAI.
"""
from typing import Dict, List, Optional, Any
import json
from db.connection import connect
from db.repository import get_included_papers, save_agent_summary, save_project_overview
from agents.azure_config import chat_completion


class ReviewAgent:
    """Agent that reviews papers and extracts structured summaries."""

    def __init__(self, api_key: Optional[str] = None):
        pass

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
        pico_str = pico_context or "No specific PICO context provided."

        prompt = f"""Extract structured information from this research paper.

Title: {title}
Abstract: {abstract}
PICO Context: {pico_str}

Extract:
- population: Population studied (patients, participants, etc.)
- intervention: Intervention or treatment being studied
- comparator: Comparison or control group
- outcomes: Outcomes measured
- main_findings: Main findings or conclusions
- sample_size: Sample size or number of participants

Respond in JSON format with these exact keys."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, temperature=0.3, max_tokens=512)

        try:
            result = json.loads(response)
            return {
                "population": result.get("population", ""),
                "intervention": result.get("intervention", ""),
                "comparator": result.get("comparator", ""),
                "outcomes": result.get("outcomes", ""),
                "main_findings": result.get("main_findings", ""),
                "sample_size": result.get("sample_size", "")
            }
        except json.JSONDecodeError:
            return {
                "population": "",
                "intervention": "",
                "comparator": "",
                "outcomes": "",
                "main_findings": "",
                "sample_size": ""
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

        prompt = f"""Generate a comprehensive overview synthesizing these paper summaries.

PICO Context: {pico_str}

Paper Summaries:
{summaries_text}

Provide a comprehensive overview synthesizing the findings across all papers."""

        messages = [
            {"role": "system", "content": "You are an expert systematic review researcher."},
            {"role": "user", "content": prompt}
        ]
        response = chat_completion(messages, temperature=0.5, max_tokens=1024)

        return response or ""


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

