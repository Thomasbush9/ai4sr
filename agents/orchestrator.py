from pathlib import Path
import os
from tqdm import tqdm
from .utils import build_pubmed_query_from_concepts, build_pubmed_query_from_keywords
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser

import pandas as pd

from .keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram, ConceptGeneratorProgram
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

    print("DEBUG: Generating keywords...")
    keyword_gen = KeywordGeneratorProgram()
    concept_gen = ConceptGeneratorProgram()
    basic_screener = Screener()  # First stage: basic screening
    cot_screener = CoTScreener()  # Second stage: detailed PICO analysis

    kw = keyword_gen.forward(query)
    boolean_keys = kw["boolean_pubmed"]  # in case you need it later
    keywords     = kw["keywords"]
    print(f"DEBUG: Generated keywords: {keywords}")

    print("DEBUG: Generating concepts...")
    concepts = concept_gen(keywords=keywords)["concepts"]
    concepts = parse_concepts(concepts)
    print(f"DEBUG: Generated concepts: {concepts}")
    
    q = build_pubmed_query_from_concepts(concepts, field="tiab", mesh_hints=None)
    print(f"DEBUG: Built PubMed query: '{q}' (length: {len(q) if q else 0})")
    
    # Fallback: if query is empty, use keywords as fallback
    if not q or not q.strip():
        print("WARNING: PubMed query is empty! Falling back to keyword-based query.")
        q = " OR ".join(keywords[:5]) if keywords else query
        print(f"DEBUG: Fallback PubMed query: '{q}'")
    
    # q = append_filters(q, english=True, humans=True, year_from=2015)

    print("DEBUG: Fetching articles from multiple sources...")
    # Use proper PubMed query for PubMed
    # For OpenAlex, use all keywords (expanded query) - better than just first 10
    openalex_query = " ".join(keywords) if keywords else query
    print(f"DEBUG: OpenAlex query (expanded keywords): {openalex_query}")
    # Default to pubmed + openalex (semantic_scholar has API issues)
    df = articles_fetchers(q, n=n, include_citations=False, sources=['pubmed', 'openalex'], 
                           pubmed_query=q, other_sources_query=openalex_query)
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
    
    # Rank all papers by relevance before screening (if we have papers)
    if not all_papers_df.empty and keywords:
        try:
            print("DEBUG: Ranking all papers by relevance before screening...")
            from .paper_finder import rank_papers_by_relevance
            query_keywords = keywords  # Use generated keywords for relevance scoring
            all_papers_df = rank_papers_by_relevance(all_papers_df, query_keywords)
            
            # Optionally limit to top N most relevant papers before screening (if too many)
            max_papers_to_screen = n * 5  # Screen up to 5x the requested number
            if len(all_papers_df) > max_papers_to_screen:
                print(f"DEBUG: Limiting to top {max_papers_to_screen} most relevant papers for screening")
                all_papers_df = all_papers_df.head(max_papers_to_screen)
            
            print(f"DEBUG: Top relevance score: {all_papers_df['relevance_score'].max() if 'relevance_score' in all_papers_df.columns else 'N/A'}")
        except Exception as e:
            print(f"DEBUG: Error in relevance ranking: {e}, continuing without ranking")
    
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
    
    # Separate included and maybe papers
    included_papers = []
    included_decisions = []
    maybe_papers = []
    maybe_decisions = []
    
    for row, decision in zip(passed_papers, passed_decisions):
        if decision["decision"] == "include":
            included_papers.append(row)
            included_decisions.append(decision)
        elif decision["decision"] == "maybe":
            maybe_papers.append(row)
            maybe_decisions.append(decision)
    
    print(f"DEBUG: Stage 1 breakdown - Included: {len(included_papers)}, Maybe: {len(maybe_papers)}")
    
    # STAGE 2: Review maybe papers with more careful screening
    print("DEBUG: Starting Stage 2 - Reviewing maybe papers...")
    reviewed_maybe_decisions = []
    for i, (row, basic_decision) in enumerate(tqdm(zip(maybe_papers, maybe_decisions), desc="Reviewing maybes")):
        title = row.title
        abstract = getattr(row, "abstract", "") or ""
        
        # Re-screen maybe papers with more context - use basic screener again but with emphasis on careful review
        try:
            # Use basic screener again but the model should be more careful with maybes
            res = basic_screener(question=query, title=title, abstract=abstract)
            
            # Ensure the result has the expected keys
            if not isinstance(res, dict):
                res = {"decision": "maybe", "score": 50}
            elif "decision" not in res:
                res["decision"] = "maybe"
            if "score" not in res:
                res["score"] = 50
                
        except Exception as e:
            print(f"DEBUG: Maybe review screener error: {e}")
            res = {"decision": "maybe", "score": 50}
        
        reviewed_maybe_decisions.append({
            "decision": res.get("decision", "maybe"),
            "score": res.get("score", 50),
            "rationale": f"Reviewed from maybe: {res.get('decision', 'maybe')}"
        })
    
    # Combine included papers with reviewed maybes for PICO analysis
    papers_for_pico = included_papers + maybe_papers
    decisions_for_pico = included_decisions + reviewed_maybe_decisions
    
    print(f"DEBUG: Stage 2 complete. {len(papers_for_pico)} papers proceeding to PICO analysis (included: {len(included_papers)}, reviewed maybes: {len(maybe_papers)})")
    
    # STAGE 3: Detailed PICO analysis with CoT screener
    print("DEBUG: Starting Stage 3 - Detailed PICO analysis...")
    final_decisions = []
    for i, (row, prev_decision) in enumerate(tqdm(zip(papers_for_pico, decisions_for_pico), desc="PICO analysis")):
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
    pico_idx = 0
    for i, basic_decision in enumerate(basic_decisions):
        if basic_decision["decision"] == "exclude":
            # This paper was excluded in basic screening
            all_decisions.append(basic_decision)
        else:
            # This paper went through maybe review and PICO analysis
            all_decisions.append(final_decisions[pico_idx])
            pico_idx += 1
    
    print(f"DEBUG: Completed screening, {len(all_decisions)} decisions made")
    print(f"DEBUG: Decisions sample: {all_decisions[:2] if all_decisions else 'No decisions'}")
    print(f"DEBUG: DataFrame shape: {all_papers_df.shape}")
    print(f"DEBUG: DataFrame columns: {all_papers_df.columns.tolist()}")
    
    print("DEBUG: Calling run_selection_and_save...")
    result = run_selection_and_save(all_papers_df, all_decisions, project_id)
    
    # Update RAG embeddings with new papers
    print("DEBUG: Updating RAG embeddings...")
    try:
        # Use project-specific RAG agent for better isolation
        rag_agent = RAGAgent(project_id=project_id)
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
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': paper.get('authors', ''),
                'year': paper.get('year'),
                'venue': paper.get('venue', ''),
                'doi': paper.get('doi', ''),
                'status': paper.get('status', ''),
                'score': paper.get('score'),
                'rationale': paper.get('rationale', '')
            })
        
        # Add papers to RAG agent (batch processing)
        if papers_for_rag:
            rag_agent.add_papers(papers_for_rag, project_id)
            print(f"DEBUG: RAG embeddings updated successfully for project {project_id} ({len(papers_for_rag)} papers)")
        else:
            print(f"DEBUG: No papers to add to RAG embeddings for project {project_id}")
    except Exception as e:
        print(f"DEBUG: Warning - Failed to update RAG embeddings: {e}")
        import traceback
        traceback.print_exc()
    
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
        api_key: Not used (kept for backward compatibility, Azure agents use environment config)
    
    Returns:
        Answer string based on retrieved papers
    """
    print(f"DEBUG: RAG answering question: '{question}' for project {project_id}")
    
    try:
        # Initialize RAG agent with project-specific vector database
        rag_agent = RAGAgent(project_id=project_id)
        
        # Try to load papers and summaries (may fail if embeddings unavailable, but that's OK)
        try:
            rag_agent._load_papers_from_db(project_id)
        except Exception as e:
            print(f"DEBUG: Warning - Failed to load papers into vector DB: {e}")
            print(f"DEBUG: Will use direct DB queries instead")
        
        try:
            rag_agent._load_agent_summaries_from_db(project_id)
        except Exception as e:
            print(f"DEBUG: Warning - Failed to load summaries into vector DB: {e}")
            # Continue anyway
        
        # Answer the question using RAG (has DB fallback built-in)
        answer = rag_agent.forward(question, project_id, top_k)
        
        print(f"DEBUG: RAG answer generated successfully")
        return answer
        
    except Exception as e:
        print(f"DEBUG: RAG error: {e}")
        import traceback
        traceback.print_exc()
        
        # Last resort: try to get papers directly from DB
        try:
            from db.connection import connect
            from db.repository import list_included, list_maybe
            
            with connect() as con:
                included = list_included(con, project_id)
                maybe = list_maybe(con, project_id)
                total = len(included) + len(maybe)
                
                if total > 0:
                    return f"I encountered an error with the embedding system, but I found {total} papers in your database. Please check your Azure embedding deployment configuration. Error: {str(e)}"
                else:
                    return f"I encountered an error while answering your question: {str(e)}. Please make sure you have run a literature review first to populate the database."
        except:
            return f"I encountered an error while answering your question: {str(e)}. Please make sure you have run a literature review first to populate the database."
if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--q", type=str, required=True)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()
    query = args.q
    n = args.n

    # Use Azure-based agents
    keyword_gen = KeywordGeneratorProgram()
    concept_gen = ConceptGeneratorProgram()
    screener = Screener()
    keywords = keyword_gen.forward(query)
    boolean_keys = keywords["boolean_pubmed"]
    keywords = keywords["keywords"]

    # Generate concepts
    concepts = concept_gen(keywords=keywords)["concepts"]
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







