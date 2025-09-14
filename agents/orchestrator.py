from pathlib import Path
import os
from tqdm import tqdm
from .utils import build_pubmed_query_from_concepts, build_pubmed_query_from_keywords
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser

import dspy
import pandas as pd

from .keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram, ConceptGenerator
from .paper_finder import fetch_from_keywords, articles_fetchers, append_filters
from .utils import parse_concepts
from .screening import Screener, CoTScreener
from db.connection import connect
from db.repository import (
    get_or_create_project, bulk_ingest_from_dfs,
    list_included, list_maybe
)
from .rag_agent import RAGAgent
load_dotenv()
OPENAI_KEY= os.getenv("OPENAI_KEY")
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


def literature_review(query: str, project_id: int, n: int = 10):
    print(f"DEBUG: Starting literature review for query: '{query}', project_id: {project_id}, n: {n}")
    
    lm = dspy.LM(api_key=OPENAI_KEY, model="gpt-4o-mini", max_tokens=256)
    dspy.configure(lm=lm)

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

    print("DEBUG: Fetching articles...")
    df = articles_fetchers(q, n=n, include_citations=False)
    print(f"DEBUG: Fetched {len(df)} articles")

    # STAGE 1: Basic screening to filter out obviously irrelevant papers
    print("DEBUG: Starting Stage 1 - Basic screening...")
    basic_decisions = []
    for row in tqdm(df.itertuples(), desc="Basic screening"):
        title = row.title
        abstract = getattr(row, "abstract", "") or ""
        
        try:
            res = basic_screener(question=query, title=title, abstract=abstract)
            print(f"DEBUG: Basic screener result: {res}")
            
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
    for i, (row, decision) in enumerate(zip(df.itertuples(), basic_decisions)):
        if decision["decision"] in ["include", "maybe"]:
            passed_papers.append(row)
            passed_decisions.append(decision)
    
    print(f"DEBUG: Stage 1 complete. {len(passed_papers)} papers passed basic screening out of {len(df)}")
    
    # STAGE 2: Detailed PICO analysis with CoT screener for passed papers
    print("DEBUG: Starting Stage 2 - Detailed PICO analysis...")
    final_decisions = []
    for i, (row, basic_decision) in enumerate(tqdm(zip(passed_papers, passed_decisions), desc="PICO analysis")):
        title = row.title
        abstract = getattr(row, "abstract", "") or ""
        
        try:
            res = cot_screener(question=query, title=title, abstract=abstract)
            print(f"DEBUG: CoT screener result: {res}")
            
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
    
    # Create final decisions list that matches the original df order
    decisions = []
    passed_idx = 0
    for i, basic_decision in enumerate(basic_decisions):
        if basic_decision["decision"] in ["include", "maybe"]:
            # This paper went through CoT analysis
            decisions.append(final_decisions[passed_idx])
            passed_idx += 1
        else:
            # This paper was excluded in basic screening
            decisions.append(basic_decision)
    
    print(f"DEBUG: Completed screening, {len(decisions)} decisions made")
    print("DEBUG: Calling run_selection_and_save...")
    result = run_selection_and_save(df, decisions, project_id)
    
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

def rag_answer(question: str, project_id: int, db_conn=None, top_k: int = 5) -> str:
    """
    Answer a question using RAG on the literature review database.
    
    Args:
        question: The user's question
        project_id: The project ID to search within
        db_conn: Database connection (optional, will create if not provided)
        top_k: Number of most relevant papers to retrieve
    
    Returns:
        Answer string based on retrieved papers
    """
    print(f"DEBUG: RAG answering question: '{question}' for project {project_id}")
    
    try:
        # Initialize RAG agent
        rag_agent = RAGAgent()
        
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

    #config lm
    load_dotenv()
    OPENAI_KEY= os.getenv("OPENAI_KEY")
    lm = dspy.LM(
        api_key=OPENAI_KEY,
        model="gpt-4o-mini",
        max_tokens=256# or the exact model you're using
        )
    dspy.configure(lm=lm)

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







