import json
import dspy
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Literal
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from pydantic import BaseModel



#  - - - - - - - - --  dspy modules

class ScreenTriageSig(dspy.Signature):
    """First-pass triage of a study's title and abstract.

    Instructions:
    - Compare to the research question and inclusion hints.
    - If key info (population/intervention/outcomes) is missing, prefer 'maybe' rather than 'exclude'.
    - Return decision in {include, maybe, exclude}, a 0-100 relevance score.
    """
    research_question: str = dspy.InputField()
    title: str = dspy.InputField()
    abstract: str = dspy.InputField()

    #outputs
    decision: Literal["include", "maybe", "exclude"] = dspy.OutputField()
    score: int = dspy.OutputField(le=0, ge=100)

class Screener(dspy.Module):
    def __init__(self) -> None:
        self.predict = dspy.Predict(ScreenTriageSig)
    def forward(self, question:str, title:str, abstract:str)->Dict[str,Any]:

        out = self.predict(
                research_question=question,
                title=title or "",
                abstract = abstract or "",
                )
        return {"decison":out["decision"], "score":out["score"]}

if __name__ == "__main__":
    load_dotenv()
    OPENAI_KEY = os.getenv("OPENAI_KEY")
    QUERY= "Investigate Factors that could enhance cocaine consuption in teenagers"

    # load the papers:
    df_papers = pd.read_csv("pubmed_results.csv")

    lm = dspy.LM(
            api_key=OPENAI_KEY,
            model="gpt-4o-mini",
            max_tokens=256
            )
    dspy.configure(lm=lm)

    screener = Screener()
    decisions=[]
    for row in tqdm(df_papers.itertuples()):
        title = row.title
        abstract = row.title
        decisions.append(screener(question=QUERY, title=title, abstract=abstract))

    df_results = pd.DataFrame(decisions)
    print(df_results.head())










