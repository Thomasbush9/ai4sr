import os
from pathlib import Path
from dotenv import load_dotenv
import json
from typing import List, Dict, Any, Optional, Iterable
from agents.azure_config import chat_completion


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


class KeywordGeneratorProgram:
    """
    Expands a query/topic into keywords and boolean search strings.
    Returns a Python dict:
    {
      "keywords": List[str],
      "boolean_generic": str,
      "boolean_pubmed": str
    }
    """

    def __init__(self):
        pass

    def forward(self, sentence: str) -> Dict[str, Any]:
        prompt = f"""Expand this research question into keywords and boolean search strings.

Research question: {sentence}

Provide:
1. A JSON list of short keywords/synonyms (strings)
2. A boolean string with AND/OR and parentheses (no field tags)
3. A PubMed-ready Boolean string (no field tags)

Respond in JSON format with keys: "keywords_json" (list of strings), "boolean_generic" (string), "boolean_pubmed" (string)."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, temperature=0.5, max_tokens=512)

        keywords: List[str]
        try:
            out = json.loads(response)
            parsed = out.get("keywords_json", [])
            if isinstance(parsed, dict) and "keywords" in parsed:
                parsed = parsed["keywords"]
            if not isinstance(parsed, list):
                raise ValueError("keywords_json is not a list")
            keywords = _dedupe([str(x) for x in parsed])

            boolean_generic = (out.get("boolean_generic", "") or "").strip()
            if not boolean_generic:
                boolean_generic = _make_boolean(keywords)

            boolean_pubmed = (out.get("boolean_pubmed", "") or "").strip()
            if not boolean_pubmed:
                boolean_pubmed = boolean_generic
        except Exception:
            keywords = _fallback_keywords(sentence)
            boolean_generic = _make_boolean(keywords)
            boolean_pubmed = boolean_generic

        return {
            "keywords": keywords,
            "boolean_generic": boolean_generic,
            "boolean_pubmed": boolean_pubmed,
        }

class SynonymGeneratorProgram:
    def __init__(self) -> None:
        pass

    def forward(self, word: str, n: int, **kwargs) -> List[str]:
        prompt = f"""Generate {n} synonyms for the word: {word}

Respond with a JSON list of {n} synonym strings."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, temperature=0.7, max_tokens=256)

        try:
            synonyms = json.loads(response)
            if isinstance(synonyms, list):
                return synonyms[:n]
            elif isinstance(synonyms, dict) and "synonyms" in synonyms:
                return synonyms["synonyms"][:n]
            return [word]
        except json.JSONDecodeError:
            return [word]


class ConceptGeneratorProgram:
    """Given a list of keywords for a research question, return grouped main concepts."""

    def __init__(self):
        pass

    def __call__(self, keywords: List[str]) -> Dict[str, List[List[str]]]:
        prompt = f"""Given this list of keywords for a research question, group them into main concepts.

Keywords: {json.dumps(keywords)}

Respond with a JSON object with key "concepts" containing a list of concept groups (list of lists of strings)."""

        messages = [{"role": "user", "content": prompt}]
        response = chat_completion(messages, temperature=0.5, max_tokens=512)

        try:
            result = json.loads(response)
            if isinstance(result, dict) and "concepts" in result:
                return {"concepts": result["concepts"]}
            elif isinstance(result, list):
                return {"concepts": result}
            return {"concepts": [keywords]}
        except json.JSONDecodeError:
            return {"concepts": [keywords]}


if __name__ == "__main__":
    load_dotenv()
    kg = KeywordGeneratorProgram()
    sg = SynonymGeneratorProgram()
    cg = ConceptGeneratorProgram()
    res = kg.forward("Do SGLT2 inhibitors reduce hospitalization in adults with HFrEF?")
    concepts = cg(keywords=res["keywords"])["concepts"]
    print(concepts)





