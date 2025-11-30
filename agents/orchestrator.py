from pathlib import Path
import os
from tqdm import tqdm
from .utils import build_pubmed_query_from_concepts, build_pubmed_query_from_keywords
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser
import threading

import dspy
import pandas as pd

from .keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram, ConceptGenerator
from .paper_finder import (
    fetch_from_keywords, articles_fetchers, append_filters,
    fetch_citations, fetch_cited_by, fetch_similar_papers, fetch_openalex_work_by_id
)
from .utils import parse_concepts
from .screening import Screener, CoTScreener
from db.connection import connect
from db.repository import (
    get_or_create_project, bulk_ingest_from_dfs,
    list_included, list_maybe
)
from .rag_agent import RAGAgent

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_KEY")

# Global lock for DSPy configuration
_dspy_lock = threading.Lock()
_dspy_configured_key = None

def configure_dspy_safely(api_key: str):
    """Safely configure DSPy with the given API key, respecting threading constraints"""
    global _dspy_configured_key
    
    with _dspy_lock:
        # Only reconfigure if we're using a different key
        if _dspy_configured_key != api_key:
            lm = dspy.LM(api_key=api_key, model="gpt-4o-mini", max_tokens=256)
            dspy.configure(lm=lm)
            _dspy_configured_key = api_key

# Configure DSPy with default key at module import if available
if OPENAI_KEY and OPENAI_KEY != "your_openai_api_key_here":
    configure_dspy_safely(OPENAI_KEY)
def run_selection_and_save(
    df: pd.DataFrame,
    decisions: list[dict],
    project_id: int
):
    """
    decisions must map 1:1 to df rows.
    Required keys: decision ('include'|'maybe'|'exclude'), score (0-100).
    Optional key: rationale (str).
    """
    print(f"DEBUG: Number of decisions: {len(decisions)}")
    print(f"DEBUG: First few decisions: {decisions[:3] if decisions else 'No decisions'}")
    
    try:
        df_results = pd.DataFrame(decisions)
        print(f"DEBUG: DataFrame created successfully with columns: {df_results.columns.tolist()}")
    except Exception as e:
        print(f"DEBUG: Error creating DataFrame: {e}")
        print(f"DEBUG: Decisions structure: {[type(d) for d in decisions]}")
        raise

    selected_papers = df[df_results["decision"] == "include"]
    maybe_papers    = df[df_results["decision"] == "maybe"]
    with connect() as con:
        # IMPORTANT: we assume project already exists (id-only flow)
        # If you need to ensure it exists, do it OUTSIDE this function.
        bulk_ingest_from_dfs(con, project_id, df, df_results)
        con.commit()
        included = list_included(con, project_id)
        maybes   = list_maybe(con, project_id)

    return project_id, included, maybes, selected_papers, maybe_papers



def literature_review(query: str, project_id: int, n: int = 10, api_key: str = None):
    print(f"DEBUG: Starting literature review for query: '{query}', project_id: {project_id}, n: {n}")
    
    # Configure DSPy with user's API key if provided, otherwise use default
    key_to_use = api_key if api_key else OPENAI_KEY
    if key_to_use and key_to_use != "your_openai_api_key_here":
        configure_dspy_safely(key_to_use)
    else:
        raise ValueError("No valid API key provided. Please configure your OpenAI API key in settings.")

    print("DEBUG: Generating keywords...")
    keyword_gen = KeywordGeneratorProgram()
    concept_gen = dspy.Predict(ConceptGenerator)
    basic_screener = Screener()  # First stage: basic screening
    cot_screener = CoTScreener()  # Second stage: detailed PICO analysis

    kw = keyword_gen(query)
    boolean_keys = kw["boolean_pubmed"]  # in case you need it later
    keywords     = kw["keywords"]
    print(f"DEBUG: Generated keywords: {keywords}")

    print("DEBUG: Generating concepts...")
    concepts = concept_gen(keywords=keywords).concepts
    concepts = parse_concepts(concepts)
    print(f"DEBUG: Generated concepts: {concepts}")
    
    q = build_pubmed_query_from_concepts(concepts, field="tiab", mesh_hints=None)
    print(f"DEBUG: Built query: {q}")
    # q = append_filters(q, english=True, humans=True, year_from=2015)

    print("DEBUG: Fetching articles from multiple sources...")
    df = articles_fetchers(q, n=n, include_citations=False, sources=['pubmed', 'openalex'])
    print(f"DEBUG: Fetched {len(df)} articles from PubMed and OpenAlex")

    # Fetch citations and similar papers for ALL initial papers (before screening)
    print("DEBUG: Fetching citations and similar papers for all initial papers...")
    citation_dfs = []
    similar_dfs = []
    papers_with_ids = 0
    papers_without_ids = 0
    
    for _, row in tqdm(df.iterrows(), desc="Fetching citations and similar papers", total=len(df)):
        # Try to get OpenAlex ID from DOI, PMID, or PMCID
        work_id = None
        if "doi" in row and pd.notna(row["doi"]) and row["doi"]:
            work_id = str(row["doi"])
        elif "pmid" in row and pd.notna(row["pmid"]) and row["pmid"]:
            work_id = str(row["pmid"])
        elif "pmcid" in row and pd.notna(row["pmcid"]) and row["pmcid"]:
            work_id = str(row["pmcid"])
        
        if not work_id:
            papers_without_ids += 1
            continue
        
        papers_with_ids += 1
        try:
            # Fetch backward citations (references)
            citations_df = fetch_citations(work_id)
            if not citations_df.empty:
                citation_dfs.append(citations_df)
                print(f"DEBUG: Fetched {len(citations_df)} backward citations for {work_id}")
            
            # Fetch forward citations (cited by)
            cited_by_df = fetch_cited_by(work_id)
            if not cited_by_df.empty:
                citation_dfs.append(cited_by_df)
                print(f"DEBUG: Fetched {len(cited_by_df)} forward citations for {work_id}")
            
            # Fetch similar papers
            similar_df = fetch_similar_papers(work_id)
            if not similar_df.empty:
                similar_dfs.append(similar_df)
                print(f"DEBUG: Fetched {len(similar_df)} similar papers for {work_id}")
        except Exception as e:
            print(f"DEBUG: Error fetching citations/similar papers for {work_id}: {e}")
            continue
    
    print(f"DEBUG: Papers with valid IDs: {papers_with_ids}, without IDs: {papers_without_ids}")
    
    # Merge all citation and similar paper DataFrames
    if citation_dfs:
        citations_combined = pd.concat(citation_dfs, ignore_index=True)
        citations_combined = citations_combined.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        print(f"DEBUG: Found {len(citations_combined)} unique citation papers")
    else:
        citations_combined = pd.DataFrame()
    
    if similar_dfs:
        similar_combined = pd.concat(similar_dfs, ignore_index=True)
        similar_combined = similar_combined.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        print(f"DEBUG: Found {len(similar_combined)} unique similar papers")
    else:
        similar_combined = pd.DataFrame()
    
    # Combine all papers: initial + citations + similar
    all_papers_df = df.copy()
    initial_count = len(all_papers_df)
    
    if not citations_combined.empty:
        print(f"DEBUG: Adding {len(citations_combined)} citation papers to {initial_count} initial papers")
        # Remove papers already in df using pandas drop_duplicates
        all_papers_df = pd.concat([all_papers_df, citations_combined], ignore_index=True)
        before_dedup = len(all_papers_df)
        all_papers_df = all_papers_df.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        after_dedup = len(all_papers_df)
        print(f"DEBUG: After citation deduplication: {before_dedup} -> {after_dedup} papers")
    
    if not similar_combined.empty:
        print(f"DEBUG: Adding {len(similar_combined)} similar papers to {len(all_papers_df)} papers")
        # Remove papers already in all_papers_df
        before_dedup = len(all_papers_df)
        all_papers_df = pd.concat([all_papers_df, similar_combined], ignore_index=True)
        all_papers_df = all_papers_df.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        after_dedup = len(all_papers_df)
        print(f"DEBUG: After similar deduplication: {before_dedup} -> {after_dedup} papers")
    
    print(f"DEBUG: Total papers after adding citations/similar: {len(all_papers_df)} (initial: {initial_count}, added: {len(all_papers_df) - initial_count})")
    
    # Now screen ALL papers together (initial + citations + similar)
    print("DEBUG: Starting Stage 1 - Basic screening on all papers...")
    basic_decisions = []
    for row in tqdm(all_papers_df.itertuples(), desc="Basic screening"):
        title = row.title
        abstract = getattr(row, "abstract", "") or ""
        
        try:
            res = basic_screener(question=query, title=title, abstract=abstract)
            
            # Ensure the result has the expected keys
            if not isinstance(res, dict):
                res = {"decision": "maybe", "score": 50}
            elif "decision" not in res:
                res["decision"] = "maybe"
            if "score" not in res:
                res["score"] = 50
                
        except Exception as e:
            print(f"DEBUG: Basic screener error: {e}")
            res = {"decision": "maybe", "score": 50}

        decision = res.get("decision", "maybe")
        score = res.get("score", 50)
        
        basic_decisions.append({
            "decision": decision, 
            "score": score, 
            "rationale": "Basic screening - no detailed analysis"
        })
    
    # Filter papers that passed basic screening (include or maybe)
    passed_papers = []
    passed_decisions = []
    for i, (row, decision) in enumerate(zip(all_papers_df.itertuples(), basic_decisions)):
        if decision["decision"] in ["include", "maybe"]:
            passed_papers.append(row)
            passed_decisions.append(decision)
    
    print(f"DEBUG: Stage 1 complete. {len(passed_papers)} papers passed basic screening out of {len(all_papers_df)}")
    
    # STAGE 2: Detailed PICO analysis with CoT screener for passed papers
    print("DEBUG: Starting Stage 2 - Detailed PICO analysis...")
    final_decisions = []
    for i, (row, basic_decision) in enumerate(tqdm(zip(passed_papers, passed_decisions), desc="PICO analysis")):
        title = row.title
        abstract = getattr(row, "abstract", "") or ""
        
        try:
            res = cot_screener(question=query, title=title, abstract=abstract)
            
            # Ensure the result has the expected keys
            if not isinstance(res, dict):
                res = {"decision": "maybe", "score": 75, "rationale": "CoT analysis failed"}
            elif "decision" not in res:
                res["decision"] = "maybe"
            if "score" not in res:
                res["score"] = 75
            if "rationale" not in res:
                res["rationale"] = "No rationale provided"
                
        except Exception as e:
            print(f"DEBUG: CoT screener error: {e}")
            res = {"decision": "maybe", "score": 75, "rationale": f"CoT analysis error: {str(e)}"}

        final_decisions.append({
            "decision": res.get("decision", "maybe"),
            "score": res.get("score", 75),
            "rationale": res.get("rationale", "No rationale provided")
        })
    
    # Create final decisions list that matches the all_papers_df order
    all_decisions = []
    passed_idx = 0
    for i, basic_decision in enumerate(basic_decisions):
        if basic_decision["decision"] in ["include", "maybe"]:
            # This paper went through CoT analysis
            all_decisions.append(final_decisions[passed_idx])
            passed_idx += 1
        else:
            # This paper was excluded in basic screening
            all_decisions.append(basic_decision)
    
    print(f"DEBUG: Completed screening, {len(all_decisions)} decisions made")
    print(f"DEBUG: Decisions sample: {all_decisions[:2] if all_decisions else 'No decisions'}")
    print(f"DEBUG: DataFrame shape: {all_papers_df.shape}")
    print(f"DEBUG: DataFrame columns: {all_papers_df.columns.tolist()}")
    
    print("DEBUG: Calling run_selection_and_save...")
    result = run_selection_and_save(all_papers_df, all_decisions, project_id)
    
    # Update RAG embeddings with new papers
    print("DEBUG: Updating RAG embeddings...")
    try:
        rag_agent = RAGAgent()
        # Get the papers that were just added to the database
        with connect() as con:
            included_papers = list_included(con, project_id)
            maybe_papers = list_maybe(con, project_id)
            all_papers = included_papers + maybe_papers
        
        # Convert to the format expected by RAG agent
        papers_for_rag = []
        for paper in all_papers:
            papers_for_rag.append({
                'id': paper['id'],
                'title': paper['title'],
                'abstract': paper['abstract'],
                'authors': paper['authors'],
                'year': paper['year'],
                'venue': paper['venue'],
                'doi': paper['doi'],
                'status': paper['status'],
                'score': paper['score'],
                'rationale': paper['rationale']
            })
        
        # Add papers to RAG agent
        rag_agent.add_papers(papers_for_rag, project_id)
        print("DEBUG: RAG embeddings updated successfully")
    except Exception as e:
        print(f"DEBUG: Warning - Failed to update RAG embeddings: {e}")
    
    print(f"DEBUG: Literature review completed successfully: {result}")
    return result

def rag_answer(question: str, project_id: int, db_conn=None, top_k: int = 5, api_key: str = None) -> str:
    """
    Answer a question using RAG on the literature review database.
    
    Args:
        question: The user's question
        project_id: The project ID to search within
        db_conn: Database connection (optional, will create if not provided)
        top_k: Number of most relevant papers to retrieve
        api_key: OpenAI API key (optional, will use env var if not provided)
    
    Returns:
        Answer string based on retrieved papers
    """
    print(f"DEBUG: RAG answering question: '{question}' for project {project_id}")
    
    try:
        # Get the API key to use
        key_to_use = api_key if api_key else OPENAI_KEY
        if not key_to_use or key_to_use == "your_openai_api_key_here":
            return "Please configure your OpenAI API key in settings before using RAG mode."
        
        # Configure DSPy safely
        configure_dspy_safely(key_to_use)
        
        # Initialize RAG agent with the API key
        rag_agent = RAGAgent(api_key=key_to_use)
        
        # Load papers for the specific project only
        rag_agent._load_papers_from_db(project_id)
        
        # Answer the question using RAG
        answer = rag_agent.forward(question, project_id, top_k)
        
        print(f"DEBUG: RAG answer generated successfully")
        return answer
        
    except Exception as e:
        print(f"DEBUG: RAG error: {e}")
        return f"I encountered an error while answering your question: {str(e)}. Please make sure you have run a literature review first to populate the database."
if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--q", type=str, required=True)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()
    query = args.q
    n = args.n

    # DSPy is already configured globally at module import

    keyword_gen = KeywordGeneratorProgram()
    concept_gen = dspy.Predict(ConceptGenerator)
    screener = Screener()
    keywords = keyword_gen(query)
    boolean_keys = keywords["boolean_pubmed"]
    keywords = keywords["keywords"]

    # skip syn now
    concepts = concept_gen(keywords=keywords).concepts
    concepts = parse_concepts(concepts)
    q = build_pubmed_query_from_concepts(concepts, field="tiab", mesh_hints=None)
#    q = append_filters(q, english=True, humans=True, year_from=2015)

    # df = articles_fetchers(q, n=n, include_citations=False)
    # decisions=[]
    # for row in tqdm(df.itertuples()):
    #     title = row.title
    #     abstract = row.title
    #     decisions.append(screener(question=query, title=title, abstract=abstract))

    # # Create or get project for command line usage
    # with connect() as con:
    #     project_id = get_or_create_project(con, "trial01")
    #     con.commit()
    # project_id, included, maybes, selected, maybe = run_selection_and_save(df, decisions, project_id)
    # print(project_id, len(included), len(maybes))
    # pass the result papers to the second screener


    # print the explanation + upload the papers to the db







