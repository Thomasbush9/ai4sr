from __future__ import annotations
from dotenv import load_dotenv
from metapub import PubMedFetcher, exceptions as mp_exceptions
from datetime import datetime
from tqdm import tqdm
import pandas as pd
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .keyword_exp import KeywordGeneratorProgram
from tabulate import tabulate
from typing import Iterable, List, Dict, Optional, Union
from .utils import build_pubmed_query_from_keywords, append_filters, build_pubmed_query_from_concepts
import config
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

# ---- OpenAlex API Functions ----
def _openalex_headers() -> Dict[str, str]:
    """Get headers for OpenAlex API requests."""
    headers = {"User-Agent": "ai4sr-paper-finder/1.0"}
    if config.OPENALEX_EMAIL:
        headers["User-Agent"] += f" (mailto:{config.OPENALEX_EMAIL})"
    return headers

def _parse_openalex_work(work: Dict) -> Dict:
    """Parse OpenAlex work JSON into our standard format."""
    # Extract DOI
    doi = None
    doi_url = None
    for loc in work.get("locations", []):
        if loc.get("landing_page_url"):
            if "doi.org" in loc["landing_page_url"]:
                doi_url = loc["landing_page_url"]
                doi = loc["landing_page_url"].split("doi.org/")[-1]
                break
    
    # Extract PubMed IDs
    pmid = None
    pmcid = None
    pubmed_url = None
    for ext_id in work.get("ids", {}):
        if ext_id == "pmid":
            pmid = str(work["ids"].get("pmid", ""))
            if pmid:
                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        elif ext_id == "pmcid":
            pmcid = str(work["ids"].get("pmcid", ""))
    
    # Extract authors
    authors = None
    if work.get("authorships"):
        author_names = []
        for auth in work["authorships"]:
            author_obj = auth.get("author", {})
            if author_obj:
                display_name = author_obj.get("display_name", "")
                if display_name:
                    author_names.append(display_name)
        if author_names:
            authors = "; ".join(author_names)
    
    # Extract year
    year = None
    pub_date = work.get("publication_date")
    if pub_date:
        try:
            year = int(pub_date[:4])
        except Exception:
            pass
    
    # Extract venue (journal)
    venue = None
    if work.get("primary_location", {}).get("source"):
        venue = work["primary_location"]["source"].get("display_name")
    
    # Extract volume/issue
    volume = None
    issue = None
    if work.get("biblio"):
        volume = str(work["biblio"].get("volume", "")) or None
        issue = str(work["biblio"].get("issue", "")) or None
    
    # Extract citations count
    citations_crossref = work.get("cited_by_count")
    
    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "title": norm(work.get("title", "")),
        "abstract": norm(work.get("abstract", "")),
        "year": year,
        "authors": authors,
        "journal": norm(venue) if venue else None,
        "volume": norm(volume) if volume else None,
        "issue": norm(issue) if issue else None,
        "doi": norm(doi) if doi else None,
        "pubmed_url": pubmed_url,
        "doi_url": doi_url or (f"https://doi.org/{doi}" if doi else None),
        "citations_crossref": citations_crossref,
        "openalex_id": work.get("id"),
        "referenced_works": work.get("referenced_works", []),
        "cited_by_api_url": work.get("cited_by_api_url"),
        "related_works": work.get("related_works", []),
    }

def fetch_openalex_works(query: str, n: int = 20) -> pd.DataFrame:
    """Search OpenAlex API and return DataFrame of works."""
    records = []
    per_page = min(200, n)  # OpenAlex max per_page is 200
    pages_needed = (n + per_page - 1) // per_page
    
    for page in range(1, pages_needed + 1):
        try:
            params = {
                "search": query,
                "per_page": per_page,
                "page": page,
            }
            if config.OPENALEX_EMAIL:
                params["mailto"] = config.OPENALEX_EMAIL
            
            r = requests.get(
                "https://api.openalex.org/works",
                params=params,
                headers=_openalex_headers(),
                timeout=30,
            )
            
            if r.status_code != 200:
                break
                
            data = r.json()
            results = data.get("results", [])
            
            if not results:
                break
            
            for work in results:
                if len(records) >= n:
                    break
                try:
                    parsed = _parse_openalex_work(work)
                    records.append(parsed)
                except Exception as e:
                    continue
            
            if len(records) >= n:
                break
                
            time.sleep(config.OPENALEX_REQUEST_DELAY)
            
        except Exception as e:
            break
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref",
        "openalex_id", "referenced_works", "cited_by_api_url", "related_works"
    ])
    
    return df

def fetch_openalex_work_by_id(work_id: str) -> Optional[Dict]:
    """Fetch a single OpenAlex work by ID (can be OpenAlex ID, DOI, or PMID)."""
    try:
        # Normalize work_id to OpenAlex API URL format
        if work_id.startswith("https://openalex.org/"):
            api_url = work_id
        elif work_id.startswith("W") and not work_id.startswith("https://"):
            api_url = f"https://openalex.org/{work_id}"
        elif work_id.startswith("10.") and not work_id.startswith("https://"):
            api_url = f"https://api.openalex.org/works/https://doi.org/{work_id}"
        elif work_id.startswith("https://doi.org/"):
            api_url = f"https://api.openalex.org/works/{work_id}"
        elif work_id.isdigit():
            api_url = f"https://api.openalex.org/works/https://pubmed.ncbi.nlm.nih.gov/{work_id}"
        elif work_id.startswith("https://pubmed.ncbi.nlm.nih.gov/"):
            api_url = f"https://api.openalex.org/works/{work_id}"
        else:
            # Try as OpenAlex ID
            api_url = f"https://api.openalex.org/works/{work_id}"
        
        params = {}
        if config.OPENALEX_EMAIL:
            params["mailto"] = config.OPENALEX_EMAIL
        
        r = requests.get(
            api_url,
            params=params,
            headers=_openalex_headers(),
            timeout=30,
        )
        
        if r.status_code == 200:
            work = r.json()
            return _parse_openalex_work(work)
    except Exception as e:
        pass
    return None

def fetch_citations(work_id: str, max_results: int = None) -> pd.DataFrame:
    """Fetch backward citations (referenced works) from OpenAlex."""
    max_results = max_results or config.MAX_CITATIONS_BACKWARD
    work = fetch_openalex_work_by_id(work_id)
    if not work or not work.get("referenced_works"):
        return pd.DataFrame()
    
    records = []
    referenced_ids = work["referenced_works"][:max_results]
    
    for ref_id in tqdm(referenced_ids, desc="Fetching citations"):
        try:
            ref_work = fetch_openalex_work_by_id(ref_id)
            if ref_work:
                # Remove OpenAlex-specific fields for consistency
                ref_work.pop("openalex_id", None)
                ref_work.pop("referenced_works", None)
                ref_work.pop("cited_by_api_url", None)
                ref_work.pop("related_works", None)
                records.append(ref_work)
            time.sleep(config.OPENALEX_REQUEST_DELAY)
        except Exception:
            continue
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref"
    ])
    return df

def fetch_cited_by(work_id: str, max_results: int = None) -> pd.DataFrame:
    """Fetch forward citations (cited by) from OpenAlex."""
    max_results = max_results or config.MAX_CITATIONS_FORWARD
    work = fetch_openalex_work_by_id(work_id)
    if not work or not work.get("cited_by_api_url"):
        return pd.DataFrame()
    
    records = []
    cited_by_url = work["cited_by_api_url"]
    
    try:
        params = {"per_page": min(200, max_results)}
        if config.OPENALEX_EMAIL:
            params["mailto"] = config.OPENALEX_EMAIL
        
        r = requests.get(
            cited_by_url,
            params=params,
            headers=_openalex_headers(),
            timeout=30,
        )
        
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])[:max_results]
            
            for cited_work in tqdm(results, desc="Fetching cited-by"):
                try:
                    parsed = _parse_openalex_work(cited_work)
                    # Remove OpenAlex-specific fields
                    parsed.pop("openalex_id", None)
                    parsed.pop("referenced_works", None)
                    parsed.pop("cited_by_api_url", None)
                    parsed.pop("related_works", None)
                    records.append(parsed)
                except Exception:
                    continue
                time.sleep(config.OPENALEX_REQUEST_DELAY)
    except Exception:
        pass
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref"
    ])
    return df

def fetch_similar_papers(work_id: str, max_results: int = None) -> pd.DataFrame:
    """Fetch similar papers (related works) from OpenAlex."""
    max_results = max_results or config.MAX_SIMILAR_PAPERS
    work = fetch_openalex_work_by_id(work_id)
    if not work or not work.get("related_works"):
        return pd.DataFrame()
    
    records = []
    related_ids = work["related_works"][:max_results]
    
    for rel_id in tqdm(related_ids, desc="Fetching similar papers"):
        try:
            rel_work = fetch_openalex_work_by_id(rel_id)
            if rel_work:
                # Remove OpenAlex-specific fields
                rel_work.pop("openalex_id", None)
                rel_work.pop("referenced_works", None)
                rel_work.pop("cited_by_api_url", None)
                rel_work.pop("related_works", None)
                records.append(rel_work)
            time.sleep(config.OPENALEX_REQUEST_DELAY)
        except Exception:
            continue
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref"
    ])
    return df

def _fetch_pubmed(query: str, n: int, include_citations: bool) -> pd.DataFrame:
    """Fetch papers from PubMed."""
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
    return df

def _fetch_openalex_simple(query: str, n: int) -> pd.DataFrame:
    """Fetch papers from OpenAlex and return in standard format (without OpenAlex-specific fields)."""
    df = fetch_openalex_works(query, n)
    if df.empty:
        return df
    
    # Remove OpenAlex-specific columns for consistency
    cols_to_drop = ["openalex_id", "referenced_works", "cited_by_api_url", "related_works"]
    for col in cols_to_drop:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    return df

# function to extract refs
def articles_fetchers(
    query: str, 
    n: int = 20, 
    include_citations: bool = True, 
    save: bool = False,
    sources: List[str] = None
):
    """
    Fetch articles from multiple sources.
    
    Args:
        query: Search query string
        n: Maximum number of results per source
        include_citations: Whether to fetch citation counts (PubMed only)
        save: Whether to save results to CSV
        sources: List of sources to use. Options: 'pubmed', 'openalex'. Default: ['pubmed', 'openalex']
    
    Returns:
        DataFrame with merged results from all sources
    """
    if sources is None:
        sources = ['pubmed', 'openalex']
    
    sources = [s.lower() for s in sources]
    dfs = []
    
    def fetch_pubmed_wrapper():
        try:
            return _fetch_pubmed(query, n, include_citations)
        except Exception as e:
            print(f"Error fetching from PubMed: {e}")
            return pd.DataFrame()
    
    def fetch_openalex_wrapper():
        try:
            return _fetch_openalex_simple(query, n)
        except Exception as e:
            print(f"Error fetching from OpenAlex: {e}")
            return pd.DataFrame()
    
    # Fetch from sources in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        if 'pubmed' in sources:
            futures['pubmed'] = executor.submit(fetch_pubmed_wrapper)
        if 'openalex' in sources:
            futures['openalex'] = executor.submit(fetch_openalex_wrapper)
        
        for source, future in futures.items():
            try:
                df = future.result()
                if not df.empty:
                    dfs.append(df)
            except Exception as e:
                print(f"Error getting results from {source}: {e}")
    
    # Merge results
    if not dfs:
        df = pd.DataFrame(columns=[
            "pmid","pmcid","title","abstract","year","authors","journal","volume","issue",
            "doi","pubmed_url","doi_url","citations_crossref"
        ])
    else:
        df = pd.concat(dfs, ignore_index=True)
        
        # Deduplicate based on DOI, PMID, or PMCID
        # Keep first occurrence
        df = df.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        
        # Limit to requested number
        if len(df) > n:
            df = df.head(n)

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



