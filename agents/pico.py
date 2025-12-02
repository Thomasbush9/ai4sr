"""
PICO (Population, Intervention, Comparison, Outcome) data model and DSPy expansion.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
import dspy
from dotenv import load_dotenv
import os
import threading

load_dotenv()

# Thread-local storage for DSPy configuration
_thread_local = threading.local()

def configure_dspy_safely(api_key: str):
    """
    Safely configure DSPy with the given API key, handling thread-local constraints.
    DSPy settings are thread-local, so we need to handle cases where configuration
    is attempted from a different thread than the initial configuration.
    """
    # Check if already configured in this thread with the same key
    if hasattr(_thread_local, 'dspy_configured_key') and _thread_local.dspy_configured_key == api_key:
        return  # Already configured in this thread
    
    # Check if DSPy is already configured in this thread
    try:
        # Try to access dspy.settings to see if it's configured
        current_lm = getattr(dspy.settings, 'lm', None) if hasattr(dspy, 'settings') else None
        if current_lm is not None:
            # DSPy is already configured - we can't change it
            # Store the key we wanted to use and continue with existing config
            _thread_local.dspy_configured_key = api_key
            return
    except (AttributeError, RuntimeError):
        pass
    
    # Try to configure DSPy
    try:
        lm = dspy.LM(api_key=api_key, model="gpt-4o-mini", max_tokens=2048)
        dspy.configure(lm=lm)
        _thread_local.dspy_configured_key = api_key
    except RuntimeError as e:
        # Handle the specific error: "dspy.settings can only be changed by the thread that initially configured it"
        if "can only be changed by the thread" in str(e):
            # DSPy is already configured in this thread by another module
            # We can't reconfigure, so we'll use the existing configuration
            _thread_local.dspy_configured_key = api_key
            # Note: The existing configuration will be used
        else:
            raise


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


class PICOExpansion(dspy.Signature):
    """Expand a PICO description into search queries and keywords."""
    pico_description: str = dspy.InputField(
        desc="PICO framework description: Population, Intervention, Comparison, Outcomes, Study design, Extra terms"
    )
    question_summary: str = dspy.OutputField(
        desc="1-3 sentence summary of the review question"
    )
    pubmed_query: str = dspy.OutputField(
        desc="Boolean search query suitable for PubMed (use field tags like [tiab], [mh] if needed)"
    )
    openalex_query: str = dspy.OutputField(
        desc="Search query suitable for OpenAlex (simple text query, no field tags)"
    )
    pico_keywords: str = dspy.OutputField(
        desc="JSON object with expanded keywords for each PICO component: {\"population\": [...], \"intervention\": [...], \"comparison\": [...], \"outcome\": [...], \"study_design\": [...]}"
    )


class PICOExpansionProgram(dspy.Module):
    """DSPy module for expanding PICO into search queries."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(PICOExpansion)
    
    def forward(self, pico_description: str) -> Dict[str, Any]:
        """Expand PICO description into queries and keywords."""
        result = self.predict(pico_description=pico_description)
        
        # Parse pico_keywords JSON
        pico_keywords = {}
        try:
            parsed = json.loads(result.pico_keywords)
            if isinstance(parsed, dict):
                pico_keywords = parsed
        except (json.JSONDecodeError, AttributeError):
            # Fallback: create empty structure
            pico_keywords = {
                "population": [],
                "intervention": [],
                "comparison": [],
                "outcome": [],
                "study_design": []
            }
        
        return {
            "question_summary": result.question_summary,
            "pubmed_query": result.pubmed_query,
            "openalex_query": result.openalex_query,
            "pico_keywords": pico_keywords,
        }


def expand_pico(pico: PICO, project_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Expand PICO into search queries using DSPy and store results.
    
    Args:
        pico: PICO object to expand
        project_id: Project ID to associate with expansion
        api_key: OpenAI API key (optional, uses env var if not provided)
    
    Returns:
        Dictionary with question_summary, pubmed_query, openalex_query, pico_keywords
    """
    from db.connection import connect
    from db.repository import save_pico_expansion
    
    # Get API key
    if not api_key:
        api_key = os.getenv("OPENAI_KEY")
    
    if not api_key or api_key == "your_openai_api_key_here":
        raise ValueError("No valid API key provided. Please configure your OpenAI API key.")
    
    # Configure DSPy (thread-safe)
    # This will configure DSPy for the current thread, or handle the case
    # where it's already configured by another module
    configure_dspy_safely(api_key)
    
    # Verify DSPy is configured before proceeding
    try:
        if not hasattr(dspy.settings, 'lm') or dspy.settings.lm is None:
            # Try one more time to configure
            lm = dspy.LM(api_key=api_key, model="gpt-4o-mini", max_tokens=2048)
            dspy.configure(lm=lm)
    except (AttributeError, RuntimeError) as e:
        if "can only be changed by the thread" not in str(e):
            raise ValueError(f"Failed to configure DSPy: {e}")
        # If it's the thread error, continue - DSPy should be configured
    
    # Convert PICO to description
    pico_description = pico_to_description(pico)
    
    # Run expansion - DSPy will use the configured LM from dspy.settings
    expansion_program = PICOExpansionProgram()
    expansion_result = expansion_program.forward(pico_description)
    
    # Store in database
    with connect() as con:
        save_pico_expansion(con, project_id, expansion_result)
        con.commit()
    
    return expansion_result

