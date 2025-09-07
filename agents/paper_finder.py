# Improved PubMed fetcher: builds a clean DataFrame with title, abstract, year,
# authors, journal, volume, issue, DOI, PubMed/DOI links, and (optionally) citation counts via Crossref.

# pip install metapub pandas tqdm python-dotenv requests

from dotenv import load_dotenv
from metapub import PubMedFetcher, exceptions as mp_exceptions
from tqdm import tqdm
import pandas as pd
import requests
import time
from keyword_exp import KeywordGeneratorProgram
from tabulate import tabulate

# ---- Config ----
KEYWORD = "Cocaine consumption"
NUM_ARTICLES = 10
INCLUDE_CITATIONS = True   # set False to skip Crossref calls (faster)
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

# ---- Main ----
if __name__ == "__main__":
    load_dotenv()

    fetch = PubMedFetcher()
    pmids = fetch.pmids_for_query(KEYWORD, retmax=NUM_ARTICLES) or []
    pmids = list(dict.fromkeys(pmids))  # de-duplicate but keep order

    records = []
    for pmid in tqdm(pmids, desc="Fetching PubMed records"):
        try:
            art = fetch.article_by_pmid(pmid)
        except mp_exceptions.MetaPubError:
            continue  # skip records we can't resolve
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
        if INCLUDE_CITATIONS and doi:
            cites = crossref_citations(doi)
            time.sleep(REQUEST_DELAY)

        records.append(
            {
                "pmid": pmid,
                "pmcid": pmcid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "authors": authors,
                "journal": journal,
                "volume": volume,
                "issue": issue,
                "doi": doi,
                "pubmed_url": pubmed_url,
                "doi_url": doi_url,
                "citations_crossref": cites,
            }
        )

    df = pd.DataFrame.from_records(records, columns=[
        "pmid","pmcid","title","abstract","year","authors","journal","volume","issue","doi","pubmed_url","doi_url","citations_crossref"
    ])

    # Preview + (optional) save
    print(tabulate(df.head(10), headers="keys", tablefmt="psql"))
    df.to_csv("pubmed_results.csv", index=False)

