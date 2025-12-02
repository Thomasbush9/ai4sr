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

# ---- Relevance Ranking ----
def calculate_relevance_score(row: pd.Series, query_keywords: List[str] = None) -> float:
    """
    Calculate relevance score for a paper based on multiple factors.
    
    Factors:
    - Citation count (normalized, 0-1 scale)
    - Publication year (recent = higher score)
    - Keyword match density in title/abstract
    - Source quality indicators
    """
    score = 0.0
    
    # 1. Citation count (0-40 points, normalized to max 1000 citations)
    citations = row.get("citations_crossref", 0) or 0
    citation_score = min(40, (citations / 1000.0) * 40) if citations else 0
    score += citation_score
    
    # 2. Publication year (0-20 points, recent = higher)
    year = row.get("year")
    if year:
        current_year = datetime.now().year
        years_ago = current_year - year
        if years_ago <= 2:
            year_score = 20
        elif years_ago <= 5:
            year_score = 15
        elif years_ago <= 10:
            year_score = 10
        else:
            year_score = max(0, 10 - (years_ago - 10) * 0.5)
        score += year_score
    
    # 3. Keyword match density (0-30 points)
    if query_keywords:
        title = str(row.get("title", "")).lower()
        abstract = str(row.get("abstract", "")).lower()
        text = f"{title} {abstract}"
        
        matches = sum(1 for kw in query_keywords if kw.lower() in text)
        keyword_score = min(30, (matches / len(query_keywords)) * 30) if query_keywords else 0
        score += keyword_score
    
    # 4. Title match bonus (0-10 points)
    if query_keywords and row.get("title"):
        title_lower = str(row.get("title", "")).lower()
        title_matches = sum(1 for kw in query_keywords if kw.lower() in title_lower)
        if title_matches > 0:
            title_bonus = min(10, (title_matches / len(query_keywords)) * 10)
            score += title_bonus
    
    return score

def rank_papers_by_relevance(df: pd.DataFrame, query_keywords: List[str] = None) -> pd.DataFrame:
    """Rank papers by relevance score and return sorted DataFrame."""
    if df.empty:
        return df
    
    # Calculate relevance scores
    df["relevance_score"] = df.apply(
        lambda row: calculate_relevance_score(row, query_keywords),
        axis=1
    )
    
    # Sort by relevance score (descending)
    df = df.sort_values(
        by="relevance_score",
        ascending=False,
        na_position='last'
    ).reset_index(drop=True)
    
    return df

# ---- Semantic Scholar Integration ----
def _parse_semantic_scholar_paper(paper: Dict) -> Dict:
    """Parse Semantic Scholar paper JSON into our standard format."""
    # Extract DOI
    doi = None
    doi_url = None
    if paper.get("externalIds", {}).get("DOI"):
        doi = paper["externalIds"]["DOI"]
        doi_url = f"https://doi.org/{doi}"
    
    # Extract PubMed IDs
    pmid = None
    pmcid = None
    pubmed_url = None
    if paper.get("externalIds", {}).get("PubMed"):
        pmid = str(paper["externalIds"]["PubMed"])
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    if paper.get("externalIds", {}).get("PubMedCentral"):
        pmcid = str(paper["externalIds"]["PubMedCentral"])
    
    # Extract authors
    authors = None
    if paper.get("authors"):
        author_names = []
        for auth in paper["authors"]:
            name = auth.get("name", "")
            if name:
                author_names.append(name)
        if author_names:
            authors = "; ".join(author_names)
    
    # Extract year
    year = None
    if paper.get("year"):
        try:
            year = int(paper["year"])
        except Exception:
            pass
    
    # Extract venue (journal)
    venue = None
    if paper.get("venue"):
        venue = paper["venue"]
    
    # Extract citations count
    citations_crossref = paper.get("citationCount", 0)
    
    # Extract relevance score if available
    relevance_score = paper.get("relevanceScore", None)
    
    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "title": norm(paper.get("title", "")),
        "abstract": norm(paper.get("abstract", "")),
        "year": year,
        "authors": authors,
        "journal": norm(venue) if venue else None,
        "volume": None,
        "issue": None,
        "doi": norm(doi) if doi else None,
        "pubmed_url": pubmed_url,
        "doi_url": doi_url,
        "citations_crossref": citations_crossref,
        "semantic_scholar_id": paper.get("paperId"),
        "semantic_scholar_url": f"https://www.semanticscholar.org/paper/{paper.get('paperId')}" if paper.get("paperId") else None,
        "relevance_score": relevance_score,
    }

def fetch_semantic_scholar_papers(query: str, n: int = 20) -> pd.DataFrame:
    """Search Semantic Scholar API and return DataFrame of papers."""
    # Semantic Scholar API is currently having issues, disable by default
    # Can be enabled later when API is stable
    print("DEBUG: Semantic Scholar is currently disabled due to API issues")
    return pd.DataFrame()
    
    # Disabled code below - re-enable when API is fixed
    """
    records = []
    offset = 0
    limit = min(100, n)  # Semantic Scholar max per request is 100
    
    headers = {"User-Agent": "ai4sr-paper-finder/1.0 (mailto:thomasbush52@gmail.com)"}
    if config.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY
    
    try:
        # Simplified fields - remove problematic ones
        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": "title,abstract,authors,year,venue,externalIds,citationCount,paperId"
        }
        
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            headers=headers,
            timeout=30,
        )
        
        if r.status_code != 200:
            error_msg = r.text if hasattr(r, 'text') else str(r.status_code)
            print(f"DEBUG: Semantic Scholar API returned status {r.status_code}: {error_msg}")
            return pd.DataFrame()
        
        data = r.json()
        results = data.get("data", [])
        
        for paper in results[:n]:
            try:
                parsed = _parse_semantic_scholar_paper(paper)
                records.append(parsed)
            except Exception as e:
                print(f"DEBUG: Error parsing Semantic Scholar paper: {e}")
                continue
        
        time.sleep(config.SEMANTIC_SCHOLAR_REQUEST_DELAY)
        
    except Exception as e:
        print(f"DEBUG: Error fetching from Semantic Scholar: {e}")
        return pd.DataFrame()
    """
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref",
        "semantic_scholar_id", "semantic_scholar_url", "relevance_score"
    ])
    
    # Sort by relevance score if available, otherwise by citations
    if "relevance_score" in df.columns and df["relevance_score"].notna().any():
        df = df.sort_values(
            by=["relevance_score", "citations_crossref"],
            ascending=[False, False],
            na_position='last'
        ).reset_index(drop=True)
    else:
        df = df.sort_values(
            by="citations_crossref",
            ascending=False,
            na_position='last'
        ).reset_index(drop=True)
    
    return df

def _fetch_semantic_scholar_simple(query: str, n: int) -> pd.DataFrame:
    """Fetch papers from Semantic Scholar and return in standard format."""
    df = fetch_semantic_scholar_papers(query, n)
    if df.empty:
        print(f"DEBUG: Semantic Scholar returned 0 results for query: {query}")
        return df
    
    print(f"DEBUG: Semantic Scholar returned {len(df)} results")
    
    # Remove Semantic Scholar-specific columns for consistency (keep semantic_scholar_url)
    cols_to_drop = ["semantic_scholar_id", "relevance_score"]
    for col in cols_to_drop:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    return df

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

def fetch_openalex_works(query: str, n: int = 20, search_strategy: str = "broad") -> pd.DataFrame:
    """
    Search OpenAlex API with improved search strategies.
    
    Args:
        query: Search query string
        n: Maximum number of results
        search_strategy: One of 'broad', 'title', 'abstract', 'all'
          - 'broad': General search across all fields
          - 'title': Search in title only
          - 'abstract': Search in abstract only
          - 'all': Combine all strategies and merge results
    """
    if search_strategy == "all":
        # Use multiple strategies and combine
        dfs = []
        for strategy in ["broad", "title", "abstract"]:
            df = fetch_openalex_works(query, n=n, search_strategy=strategy)
            if not df.empty:
                dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        # Combine and deduplicate
        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        
        # Sort by relevance (citations, then year)
        combined = combined.sort_values(
            by=['citations_crossref', 'year'],
            ascending=[False, False],
            na_position='last'
        ).reset_index(drop=True)
        
        return combined.head(n)
    
    records = []
    per_page = min(200, n)  # OpenAlex max per_page is 200
    pages_needed = (n + per_page - 1) // per_page
    
    # Build search query based on strategy
    if search_strategy == "title":
        search_query = f"title.search:{query}"
    elif search_strategy == "abstract":
        search_query = f"abstract.search:{query}"
    else:  # broad
        search_query = query
    
    for page in range(1, pages_needed + 1):
        try:
            params = {
                "search": search_query,
                "per_page": per_page,
                "page": page,
                "sort": "cited_by_count:desc",  # Sort by citations (relevance)
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
                print(f"DEBUG: OpenAlex API returned status {r.status_code}")
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
            print(f"DEBUG: Error in OpenAlex search: {e}")
            break
    
    df = pd.DataFrame.from_records(records, columns=[
        "pmid", "pmcid", "title", "abstract", "year", "authors", "journal",
        "volume", "issue", "doi", "pubmed_url", "doi_url", "citations_crossref",
        "openalex_id", "referenced_works", "cited_by_api_url", "related_works"
    ])
    
    # Sort by citations if not already sorted
    if not df.empty:
        df = df.sort_values(
            by='citations_crossref',
            ascending=False,
            na_position='last'
        ).reset_index(drop=True)
    
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
    if not query or not query.strip():
        print("ERROR: PubMed query is empty!")
        return pd.DataFrame()
    
    print(f"DEBUG: _fetch_pubmed called with query: '{query}', n={n}")
    fetch = PubMedFetcher()
    
    try:
        pmids = fetch.pmids_for_query(query, retmax=n) or []
    except Exception as e:
        print(f"ERROR: pmids_for_query failed: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    
    pmids = list(dict.fromkeys(pmids))
    
    print(f"DEBUG: PubMed found {len(pmids)} PMIDs for query '{query}'")

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
    print(f"DEBUG: PubMed successfully fetched {len(df)} records")
    return df

def _fetch_openalex_simple(query: str, n: int) -> pd.DataFrame:
    """Fetch papers from OpenAlex - use broad search for simplicity and reliability."""
    # Use 'broad' strategy for simplicity (multiple strategies can be slow and error-prone)
    df = fetch_openalex_works(query, n=n, search_strategy="broad")
    if df.empty:
        print(f"DEBUG: OpenAlex returned 0 results for query: {query}")
        return df
    
    print(f"DEBUG: OpenAlex returned {len(df)} results")
    
    # Keep openalex_id for tracking, but remove other OpenAlex-specific fields
    cols_to_drop = ["referenced_works", "cited_by_api_url", "related_works"]
    for col in cols_to_drop:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    # Add openalex_url for papers that have openalex_id
    if "openalex_id" in df.columns:
        df["openalex_url"] = df["openalex_id"].apply(
            lambda x: f"https://openalex.org/{x.split('/')[-1]}" if x and pd.notna(x) else None
        )
    
    return df

# function to extract refs
def articles_fetchers(
    query: str, 
    n: int = 20, 
    include_citations: bool = True, 
    save: bool = False,
    sources: List[str] = None,
    pubmed_query: str = None,
    other_sources_query: str = None
):
    """
    Fetch articles from multiple sources.
    
    Args:
        query: Default search query string (used if source-specific queries not provided)
        n: Maximum number of results per source
        include_citations: Whether to fetch citation counts (PubMed only)
        save: Whether to save results to CSV
        sources: List of sources to use. Options: 'pubmed', 'openalex', 'semantic_scholar'. 
                Default: ['pubmed', 'openalex']
        pubmed_query: Specific query for PubMed (uses complex format). If None, uses query.
        other_sources_query: Query for OpenAlex/Semantic Scholar (simple format). If None, uses query.
    
    Returns:
        DataFrame with merged results from all sources, ranked by relevance
    """
    if sources is None:
        sources = ['pubmed', 'openalex']
    
    sources = [s.lower() for s in sources]
    # Remove semantic_scholar if present (currently disabled due to API issues)
    if 'semantic_scholar' in sources:
        sources.remove('semantic_scholar')
        print("DEBUG: Semantic Scholar removed from sources (currently disabled)")
    
    dfs = []
    
    # Use source-specific queries if provided, otherwise use default query
    pubmed_q = pubmed_query if pubmed_query is not None else query
    other_q = other_sources_query if other_sources_query is not None else query
    
    # Extract keywords from query for relevance ranking
    query_keywords = other_q.lower().split() if other_sources_query else query.lower().split()
    
    def fetch_pubmed_wrapper():
        try:
            print(f"DEBUG: PubMed query being used: '{pubmed_q}'")
            return _fetch_pubmed(pubmed_q, n, include_citations)
        except Exception as e:
            print(f"ERROR: Exception fetching from PubMed: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def fetch_openalex_wrapper():
        try:
            return _fetch_openalex_simple(other_q, n)
        except Exception as e:
            print(f"Error fetching from OpenAlex: {e}")
            return pd.DataFrame()
    
    def fetch_semantic_scholar_wrapper():
        try:
            return _fetch_semantic_scholar_simple(other_q, n)
        except Exception as e:
            print(f"Error fetching from Semantic Scholar: {e}")
            return pd.DataFrame()
    
    # Fetch from sources in parallel
    max_workers = min(len([s for s in sources if s in ['pubmed', 'openalex']]), 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        if 'pubmed' in sources:
            futures['pubmed'] = executor.submit(fetch_pubmed_wrapper)
        if 'openalex' in sources:
            futures['openalex'] = executor.submit(fetch_openalex_wrapper)
        # Semantic Scholar disabled for now
        # if 'semantic_scholar' in sources:
        #     futures['semantic_scholar'] = executor.submit(fetch_semantic_scholar_wrapper)
        
        for source, future in futures.items():
            try:
                df = future.result()
                if not df.empty:
                    print(f"DEBUG: {source.capitalize()} returned {len(df)} papers")
                    # Add source column to track origin
                    df["source"] = source
                    dfs.append(df)
                else:
                    print(f"DEBUG: {source.capitalize()} returned 0 papers")
            except Exception as e:
                print(f"Error getting results from {source}: {e}")
    
    # Merge results
    if not dfs:
        df = pd.DataFrame(columns=[
            "pmid","pmcid","title","abstract","year","authors","journal","volume","issue",
            "doi","pubmed_url","doi_url","citations_crossref","source","openalex_url","semantic_scholar_url"
        ])
    else:
        df = pd.concat(dfs, ignore_index=True)
        
        # Count papers by source before deduplication
        if "source" in df.columns:
            source_counts = df["source"].value_counts()
            print(f"DEBUG: Papers by source before deduplication: {dict(source_counts)}")
        
        # Deduplicate based on DOI, PMID, or PMCID
        # Keep first occurrence (which will be PubMed if both sources have the same paper)
        before_dedup = len(df)
        df = df.drop_duplicates(
            subset=['doi', 'pmid', 'pmcid'],
            keep='first'
        ).reset_index(drop=True)
        after_dedup = len(df)
        print(f"DEBUG: Deduplication: {before_dedup} -> {after_dedup} papers (removed {before_dedup - after_dedup} duplicates)")
        
        # Count papers by source after deduplication
        if "source" in df.columns:
            source_counts = df["source"].value_counts()
            print(f"DEBUG: Papers by source after deduplication: {dict(source_counts)}")
        
        # Set url field to openalex_url or semantic_scholar_url if no doi_url or pubmed_url
        if "openalex_url" in df.columns or "semantic_scholar_url" in df.columns:
            def set_url(row):
                if pd.notna(row.get("doi_url")):
                    return row.get("doi_url")
                elif pd.notna(row.get("pubmed_url")):
                    return row.get("pubmed_url")
                elif pd.notna(row.get("openalex_url")):
                    return row.get("openalex_url")
                elif pd.notna(row.get("semantic_scholar_url")):
                    return row.get("semantic_scholar_url")
                return row.get("url") if "url" in row else None
            
            df["url"] = df.apply(set_url, axis=1)
        
        # Rank papers by relevance before limiting (only if we have papers and keywords)
        if not df.empty and query_keywords:
            try:
                df = rank_papers_by_relevance(df, query_keywords)
                print(f"DEBUG: Ranked papers by relevance (top score: {df['relevance_score'].max() if 'relevance_score' in df.columns else 'N/A'})")
            except Exception as e:
                print(f"DEBUG: Error in relevance ranking: {e}, continuing without ranking")
        
        # Limit to requested number (after ranking)
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



