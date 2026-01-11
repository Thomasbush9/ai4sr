"""
PICO (Population, Intervention, Comparison, Outcome) data model and expansion using Azure OpenAI.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
from dotenv import load_dotenv
import os
from agents.azure_config import chat_completion

load_dotenv()


@dataclass
class PICO:
    """PICO framework for systematic review questions."""
    population: str
    intervention: Optional[str] = None
    comparison: Optional[str] = None
    outcome: Optional[str] = None
    study_design: Optional[str] = None
    extra_terms: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert PICO to dictionary for JSON serialization."""
        return {
            "population": self.population,
            "intervention": self.intervention,
            "comparison": self.comparison,
            "outcome": self.outcome,
            "study_design": self.study_design,
            "extra_terms": self.extra_terms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PICO":
        """Create PICO from dictionary."""
        return cls(
            population=data.get("population", ""),
            intervention=data.get("intervention"),
            comparison=data.get("comparison"),
            outcome=data.get("outcome"),
            study_design=data.get("study_design"),
            extra_terms=data.get("extra_terms"),
        )


def pico_to_description(pico: PICO) -> str:
    """
    Convert PICO object to a text description for DSPy input.
    
    Format: "Population: ... | Intervention: ... | Comparison: ... | Outcomes: ... | Study design: ... | Extra terms: ..."
    """
    parts = []
    
    if pico.population:
        parts.append(f"Population: {pico.population}")
    
    if pico.intervention:
        parts.append(f"Intervention: {pico.intervention}")
    
    if pico.comparison:
        parts.append(f"Comparison: {pico.comparison}")
    
    if pico.outcome:
        parts.append(f"Outcomes: {pico.outcome}")
    
    if pico.study_design:
        parts.append(f"Study design: {pico.study_design}")
    
    if pico.extra_terms:
        terms_str = ", ".join(pico.extra_terms) if isinstance(pico.extra_terms, list) else str(pico.extra_terms)
        parts.append(f"Extra terms: {terms_str}")
    
    return " | ".join(parts)


class PICOExpansionProgram:
    """Module for expanding PICO into search queries using Azure OpenAI."""

    def __init__(self):
        pass

    def forward(self, pico_description: str) -> Dict[str, Any]:
        """Expand PICO description into queries and keywords."""
        print(f"DEBUG: Expanding PICO description: {pico_description[:100]}...", flush=True)
        
        prompt = f"""Expand this PICO framework description into search queries and keywords.

PICO Description: {pico_description}

Provide:
1. question_summary: 1-3 sentence summary of the review question
2. pubmed_query: Boolean search query suitable for PubMed (use field tags like [tiab], [mh] if needed)
3. openalex_query: Search query suitable for OpenAlex (simple text query, no field tags)
4. pico_keywords: JSON object with expanded keywords for each PICO component

Respond in JSON format with keys: "question_summary" (string), "pubmed_query" (string), "openalex_query" (string), "pico_keywords" (object with keys: population, intervention, comparison, outcome, study_design - each containing a list of keyword strings)."""

        try:
            messages = [{"role": "user", "content": prompt}]
            print(f"DEBUG: Calling Azure PICO agent with prompt length {len(prompt)}...", flush=True)
            response = chat_completion(messages, agent_type="pico", timeout=90)  # 90 second timeout for PICO expansion
            print(f"DEBUG: Received response from PICO agent (length: {len(response) if response else 0})", flush=True)
            
            if not response or not response.strip():
                raise ValueError("Empty response from Azure agent")
            
            try:
                result = json.loads(response)
                pico_keywords = result.get("pico_keywords", {})
                if not isinstance(pico_keywords, dict):
                    pico_keywords = {
                        "population": [],
                        "intervention": [],
                        "comparison": [],
                        "outcome": [],
                        "study_design": []
                    }

                print(f"DEBUG: Successfully parsed PICO expansion result", flush=True)
                return {
                    "question_summary": result.get("question_summary", ""),
                    "pubmed_query": result.get("pubmed_query", ""),
                    "openalex_query": result.get("openalex_query", ""),
                    "pico_keywords": pico_keywords,
                }
            except json.JSONDecodeError as e:
                print(f"DEBUG: Failed to parse JSON response: {e}", flush=True)
                print(f"DEBUG: Response was: {response[:500]}", flush=True)
                raise ValueError(f"Failed to parse JSON response from Azure agent: {str(e)}")
        except Exception as e:
            print(f"ERROR: PICO expansion failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise


def expand_pico(pico: PICO, project_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Expand PICO into search queries using Azure OpenAI and store results.

    Args:
        pico: PICO object to expand
        project_id: Project ID to associate with expansion
        api_key: Not used (kept for backward compatibility)

    Returns:
        Dictionary with question_summary, pubmed_query, openalex_query, pico_keywords
    """
    from db.connection import connect
    from db.repository import save_pico_expansion

    # Convert PICO to description
    pico_description = pico_to_description(pico)

    # Run expansion using Azure OpenAI
    expansion_program = PICOExpansionProgram()
    expansion_result = expansion_program.forward(pico_description)

    # Store in database
    with connect() as con:
        save_pico_expansion(con, project_id, expansion_result)
        con.commit()

    return expansion_result

