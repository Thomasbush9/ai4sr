from pathlib import Path
import os
from tqdm import tqdm
from agents.utils import build_pubmed_query_from_concepts, build_pubmed_query_from_keywords
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser

import dspy
import pandas as pd

from agents.keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram, ConceptGenerator
from agents.paper_finder import fetch_from_keywords, articles_fetchers, append_filters
from agents.utils import parse_concepts
from agents.screening import Screener


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
    print(df.head())
    decisions=[]
    for row in tqdm(df.itertuples()):
        title = row.title
        abstract = row.title
        decisions.append(screener(question=query, title=title, abstract=abstract))

    df_results = pd.DataFrame(decisions)





