import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Literal
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from pydantic import BaseModel
from agents.azure_config import chat_completion


class Screener:
    def __init__(self) -> None:
        pass

    def forward(self, question: str, title: str, abstract: str) -> Dict[str, Any]:
        prompt = f"""First-pass triage of a study's title and abstract.

Instructions:
- Compare to the research question and inclusion hints.
- If key info (population/intervention/outcomes) is missing, prefer 'maybe' rather than 'exclude'.
- Return decision in {{include, maybe, exclude}}, a 0-100 relevance score.

Research question: {question}
Title: {title or ""}
Abstract: {abstract or ""}

Respond in JSON format with keys: "decision" (include/maybe/exclude) and "score" (0-100)."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, agent_type="screener")

        try:
            result = json.loads(response)
            return {"decision": result.get("decision", "maybe"), "score": int(result.get("score", 50))}
        except json.JSONDecodeError:
            return {"decision": "maybe", "score": 50}


class CoTScreener:
    def __init__(self, callbacks=None):
        pass

    def forward(self, question: str, title: str, abstract: str) -> Dict[str, Any]:
        prompt = f"""Perform detailed PICO analysis of this paper for systematic review inclusion.

PICO Framework Analysis:
- P (Population): Who is studied? Age, gender, condition, etc.
- I (Intervention/Index): What is the main intervention or exposure?
- C (Comparator): What is it compared to? Control group, alternative treatment?
- O (Outcomes): What outcomes are measured? Primary and secondary endpoints?

Based on this analysis, provide a final decision and detailed rationale.

Research question: {question}
Title: {title}
Abstract: {abstract}

Respond in JSON format with keys: "decision" (include/maybe/exclude) and "rationale" (detailed PICO analysis)."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, agent_type="cot-screener")

        try:
            result = json.loads(response)
            return {
                "decision": result.get("decision", "maybe"),
                "rationale": result.get("rationale", "Analysis not available"),
                "score": 85
            }
        except json.JSONDecodeError:
            return {
                "decision": "maybe",
                "rationale": response,
                "score": 85
            }

if __name__ == "__main__":
    load_dotenv()
    OPENAI_KEY = os.getenv("OPENAI_KEY")
    QUERY= "Investigate Factors that could enhance cocaine consuption in teenagers"

    # load the papers:
    df_papers = pd.read_csv("pubmed_results.csv")

    # Don't reconfigure DSPy - use the global configuration
    # This avoids threading issues in Docker

    screener = Screener()
    decisions=[]
    for row in tqdm(df_papers.itertuples()):
        title = row.title
        abstract = row.title
        decisions.append(screener(question=QUERY, title=title, abstract=abstract))

    df_results = pd.DataFrame(decisions)
    print(df_results.head())










