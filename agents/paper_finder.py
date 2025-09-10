from __future__ import annotations
from dotenv import load_dotenv
from metapub import PubMedFetcher, exceptions as mp_exceptions
from datetime import datetime
from tqdm import tqdm
import pandas as pd
import requests
import time
from ai4sr.agents.keyword_exp import KeywordGeneratorProgram
from tabulate import tabulate
from typing import Iterable, List, Dict, Optional, Union
from ai4sr.agents.utils import build_pubmed_query_from_keywords, append_filters, build_pubmed_query_from_concepts
# ---- Config ----
REQUEST_DELAY = 0.1        # polite delay between Crossref calls (seconds)

# ---- Helpers ----
def norm(s):
    return " ".join(s.split()) if isinstance(s, str) else s

def join_authors(art) -> str | None:
    """MetaPub 'authors' can be strings or objects; normalize to 'Last, First; ...'"""
    names = []
    try:
        for a in getattr(art, "authors", []) or []:
            if isinstance(a, str):
                names.append(norm(a))
            else:
                last = getattr(a, "lastname", "") or getattr(a, "last", "") or getattr(a, "family", "")
                first = getattr(a, "firstname", "") or getattr(a, "first", "") or getattr(a, "given", "")
                name = ", ".join([x for x in [last, first] if x])
                name = name or getattr(a, "name", "")
                if name:
                    names.append(norm(name))
    except Exception:
        return None
    return "; ".join([n for n in names if n]) or None

def get_year(art) -> int | None:
    y = getattr(art, "year", None)
    if y:
        try:
            return int(str(y)[:4])
        except Exception:
            pass
    # fallback to pubdate if available
    pubdate = getattr(art, "pubdate", None)
    try:
        return int(str(pubdate)[:4]) if pubdate else None
    except Exception:
        return None

def crossref_citations(doi: str) -> int | None:
    """Return is-referenced-by-count from Crossref, or None."""
    if not doi:
        return None
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=20,
            headers={"User-Agent": "pubmed-fetcher/1.0 (mailto:you@example.com)"},
        )
        if r.status_code == 200:
            msg = r.json().get("message", {})
            return msg.get("is-referenced-by-count")
    except Exception:
        return None
    return None

# function to extract refs
def articles_fetchers(query: str, n: int = 20, include_citations: bool = True, save: bool = False):
    fetch = PubMedFetcher()
    pmids = fetch.pmids_for_query(query, retmax=n) or []
    pmids = list(dict.fromkeys(pmids))

    records = []
    for pmid in tqdm(pmids, desc="Fetching PubMed records"):
        try:
            art = fetch.article_by_pmid(pmid)
        except mp_exceptions.MetaPubError:
            continue
        except Exception:
            continue

        title = norm(getattr(art, "title", None))
        abstract = norm(getattr(art, "abstract", None))
        journal = norm(getattr(art, "journal", None))
        volume = norm(getattr(art, "volume", None))
        issue = norm(getattr(art, "issue", None))
        doi = norm(getattr(art, "doi", None))
        pmcid = norm(getattr(art, "pmcid", None))
        year = get_year(art)
        authors = join_authors(art)
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
        doi_url = f"https://doi.org/{doi}" if doi else None

        cites = None
        if include_citations and doi:
            cites = crossref_citations(doi)
            time.sleep(REQUEST_DELAY)

        records.append({
            "pmid": pmid, "pmcid": pmcid, "title": title, "abstract": abstract, "year": year,
            "authors": authors, "journal": journal, "volume": volume, "issue": issue, "doi": doi,
            "pubmed_url": pubmed_url, "doi_url": doi_url, "citations_crossref": cites,
        })

    df = pd.DataFrame.from_records(records, columns=[
        "pmid","pmcid","title","abstract","year","authors","journal","volume","issue",
        "doi","pubmed_url","doi_url","citations_crossref"
    ])

    if save:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        df.to_csv(f"{ts}_papers.csv", index=False)

    return df

def fetch_from_keywords(keywords, *, english=False, humans=False, year_from=None, year_to=None, **kwargs):
    q = build_pubmed_query_from_keywords(keywords, field="tiab")
    q = append_filters(q, english=english, humans=humans, year_from=year_from, year_to=year_to)
    return articles_fetchers(q, **kwargs)
# ---- Main ----
if __name__ == "__main__":
    load_dotenv()
    concepts = [
    ["cocaine"],                                   # concept A (exposure)
    ["consumption", "drug use", "substance abuse", "addiction"],   # concept B (behavior)
    ["causes", "psychological factors", "socioeconomic factors"]   # concept C (factors/outcomes)
    ]
    mesh = {"cocaine": '"Cocaine"[mh]', "risk factors": '"Risk Factors"[mh]'}  # optional
    q = build_pubmed_query_from_concepts(concepts, field="tiab", mesh_hints=mesh)
    q = append_filters(q, english=True, humans=True, year_from=2015)
    df = articles_fetchers(q, n=10, include_citations=True)



