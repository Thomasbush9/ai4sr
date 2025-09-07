from pathlib import Path
import os
from tqdm import tqdm
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Literal
from argparse import ArgumentParser

import dspy
import pandas as pd

from agents.keyword_exp import KeywordGeneratorProgram, SynonymGeneratorProgram



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
    keywords = keyword_gen(query)
    boolean_keys = keywords["boolean_pubmed"]
    keywords = keywords["keywords"]
    # skip syn now
    print(f"keywords Generated:{keywords}")





