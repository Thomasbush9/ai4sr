import os
from pathlib import Path
from dotenv import load_dotenv
import dspy

# keywords_dspy.py
import json
from typing import List, Dict, Any, Optional, Iterable

import dspy


class KeywordGenerator(dspy.Signature):
    """Expand a query/topic into keywords and boolean search strings."""
    sentence: str = dspy.InputField(desc="Research question or topic (free text)")
    keywords_json: str = dspy.OutputField(
        desc="JSON list of short keywords/synonyms (strings)."
    )
    boolean_generic: str = dspy.OutputField(
        desc="Boolean string with AND/OR and parentheses (no field tags)."
    )
    boolean_pubmed: str = dspy.OutputField(
        desc="PubMed-ready Boolean string (no field tags)."
    )


def _dedupe(strings: List[str]) -> List[str]:
    seen = set()
    out = []
    for s in strings:
        if not isinstance(s, str):
            continue
        t = s.strip()
        if not t:
            continue
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def _fallback_keywords(sentence: str) -> List[str]:
    # extremely naive fallback if the LM fails to return JSON
    rough = (
        sentence.replace(",", " ")
        .replace("/", " ")
        .replace("(", " ")
        .replace(")", " ")
        .split()
    )
    # keep medium-length tokens; tweak as you like
    return _dedupe([w for w in rough if 3 <= len(w) <= 40])


def _make_boolean(terms: List[str]) -> str:
    if not terms:
        return ""
    # simple OR group; you can evolve to group by stems/synonyms later
    return "(" + " OR ".join(terms) + ")"


class KeywordGeneratorProgram(dspy.Module):
    """
    Wraps the KeywordGenerator signature and returns a Python dict:
    {
      "keywords": List[str],
      "boolean_generic": str,
      "boolean_pubmed": str
    }
    """

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(KeywordGenerator)

    def forward(self, sentence: str) -> Dict[str, Any]:
        out = self.predict(sentence=sentence)

        # parse keywords_json
        keywords: List[str]
        try:
            parsed = json.loads(out.keywords_json)
            if isinstance(parsed, dict) and "keywords" in parsed:
                parsed = parsed["keywords"]
            if not isinstance(parsed, list):
                raise ValueError("keywords_json is not a list")
            keywords = _dedupe([str(x) for x in parsed])
        except Exception:
            keywords = _fallback_keywords(sentence)

        boolean_generic = (getattr(out, "boolean_generic", "") or "").strip()
        if not boolean_generic:
            boolean_generic = _make_boolean(keywords)

        boolean_pubmed = (getattr(out, "boolean_pubmed", "") or "").strip()
        if not boolean_pubmed:
            boolean_pubmed = boolean_generic

        return {
            "keywords": keywords,
            "boolean_generic": boolean_generic,
            "boolean_pubmed": boolean_pubmed,
        }

class SynonymGenerator(dspy.Signature):
    """Generates n synonyms given a input word and a number"""
    word: str = dspy.InputField()
    n: int = dspy.InputField()
    synonyms: List[str] = dspy.OutputField()

class SynonymGeneratorProgram(dspy.Module):
    def __init__(self) -> None:
        self.synonym_generator = dspy.Predict(SynonymGenerator)
    def forward(self, word, n,  **kwargs):
        return self.synonym_generator(word=word, n=n).synonyms

class ConceptGenerator(dspy.Signature):
    """Given a list of keywords for a research question, return grouped main concepts."""
    keywords = dspy.InputField(desc="List of keywords", format=list)
    concepts = dspy.OutputField(desc="List of concept groups (list of lists)", format=list)


if __name__ == "__main__":
    load_dotenv()
    OPENAI_KEY=os.getenv("OPENAI_KEY")
    lm = dspy.LM(
        api_key=OPENAI_KEY,
        model="gpt-4o-mini",
        max_tokens=256# or the exact model you're using
    )
    dspy.configure(lm=lm)
    kg = KeywordGeneratorProgram()
    sg = SynonymGeneratorProgram()
    cg = dspy.Predict(ConceptGenerator)
    res = kg("Do SGLT2 inhibitors reduce hospitalization in adults with HFrEF?")
    # print(res["keywords"])
    # print(res["boolean_pubmed"])
    #
    # try synonyms:
    # synonyms = sg(word=res["keywords"][0], n=5)
    # print(synonyms)
    #
    # generates the concepts:
    concepts = cg(keywords=res["keywords"]).concepts
    print(concepts)





