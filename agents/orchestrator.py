from pathlib import Path
import os
from tqdm import tqdm
from ai4sr.agents.utils import build_pubmed_query_from_concepts, build_pubmed_query_from_keywords
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser

import dspy
import pandas as pd

from ai4sr.agents.keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram, ConceptGenerator
from ai4sr.agents.paper_finder import fetch_from_keywords, articles_fetchers, append_filters
from ai4sr.agents.utils import parse_concepts
from ai4sr.agents.screening import Screener
from ai4sr.db.connection import connect
from ai4sr.db.repository import (
    get_or_create_project, bulk_ingest_from_dfs,
    list_included, list_maybe
)

def run_selection_and_save(df: pd.DataFrame, decisions: list[dict], project_name: str):
    """
    decisions must map 1:1 to df rows.
    Required keys: decision ('include'|'maybe'|'exclude'), score (0-100).
    Optional key: rationale (str).
    """
    df_results = pd.DataFrame(decisions)  # may include 'rationale'

    # (Optional) keep your quick views in memory
    selected_papers = df[df_results["decision"] == "include"]
    maybe_papers    = df[df_results["decision"] == "maybe"]

    with connect() as con:
        project_id = get_or_create_project(con, project_name)
        bulk_ingest_from_dfs(con, project_id, df, df_results)   # ← persists include+maybe (+ rationale)
        con.commit()
        included = list_included(con, project_id)  # list[dict] for GUI “Selected”
        maybes   = list_maybe(con, project_id)     # list[dict] for GUI “Maybe”
    return project_id, included, maybes, selected_papers, maybe_papers


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

    df = articles_fetchers(q, n=n, include_citations=False)
    decisions=[]
    for row in tqdm(df.itertuples()):
        title = row.title
        abstract = row.title
        decisions.append(screener(question=query, title=title, abstract=abstract))

    project_id, included, maybes, selected, maybe = run_selection_and_save(df, decisions, "trial01")
    print(project_id, len(included), len(maybes))
    # pass the result papers to the second screener


    # print the explanation + upload the papers to the db







