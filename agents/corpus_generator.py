"""
Async corpus generation from PubMed and OpenAlex.
"""
import asyncio
import httpx
from typing import List, Dict, Optional, Tuple
from metapub import PubMedFetcher, exceptions as mp_exceptions
import time
from concurrent.futures import ThreadPoolExecutor
import config
from .paper_finder import norm, join_authors, get_year, crossref_citations, _openalex_headers, _parse_openalex_work


async def fetch_pubmed_async(query: str, max_results: Optional[int] = None) -> List[Dict]:
    """
    Fetch papers from PubMed asynchronously.
    
    Note: metapub doesn't support async, so we use ThreadPoolExecutor to run it in a thread.
    """
    if not query or not query.strip():
        return []
    
    max_results = max_results or 100
    
    def _fetch_sync():
        """Synchronous PubMed fetch."""
        fetch = PubMedFetcher()
        try:
            pmids = fetch.pmids_for_query(query, retmax=max_results) or []
        except Exception as e:
            print(f"ERROR: pmids_for_query failed: {e}")
            return []
        
        pmids = list(dict.fromkeys(pmids))
        records = []
        
        for pmid in pmids[:max_results]:
            try:
                art = fetch.article_by_pmid(pmid)
            except (mp_exceptions.MetaPubError, Exception):
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
            
            records.append({
                "pmid": pmid,
                "pmcid": pmcid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "authors": authors,
                "journal": journal,
                "venue": journal,  # alias for consistency
                "volume": volume,
                "issue": issue,
                "doi": doi,
                "pubmed_url": pubmed_url,
                "doi_url": doi_url,
                "url": doi_url or pubmed_url,
                "source": "pubmed",
            })
        
        return records
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        records = await loop.run_in_executor(executor, _fetch_sync)
    
    return records


async def fetch_openalex_async(query: str, max_results: Optional[int] = None) -> List[Dict]:
    """Fetch papers from OpenAlex asynchronously."""
    if not query or not query.strip():
        return []
    
    max_results = max_results or 100
    per_page = min(200, max_results)
    pages_needed = (max_results + per_page - 1) // per_page
    
    records = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for page in range(1, pages_needed + 1):
            try:
                params = {
                    "search": query,
                    "per_page": per_page,
                    "page": page,
                    "sort": "cited_by_count:desc",
                }
                if config.OPENALEX_EMAIL:
                    params["mailto"] = config.OPENALEX_EMAIL
                
                response = await client.get(
                    "https://api.openalex.org/works",
                    params=params,
                    headers=_openalex_headers(),
                )
                
                if response.status_code != 200:
                    print(f"DEBUG: OpenAlex API returned status {response.status_code}")
                    break
                
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    break
                
                for work in results:
                    if len(records) >= max_results:
                        break
                    try:
                        parsed = _parse_openalex_work(work)
                        # Add source and normalize
                        parsed["source"] = "openalex"
                        parsed["journal"] = parsed.get("journal") or parsed.get("venue")
                        parsed["url"] = parsed.get("doi_url") or parsed.get("pubmed_url")
                        # Remove OpenAlex-specific fields
                        parsed.pop("openalex_id", None)
                        parsed.pop("referenced_works", None)
                        parsed.pop("cited_by_api_url", None)
                        parsed.pop("related_works", None)
                        records.append(parsed)
                    except Exception as e:
                        continue
                
                if len(records) >= max_results:
                    break
                
                # Rate limiting
                await asyncio.sleep(config.OPENALEX_REQUEST_DELAY)
                
            except Exception as e:
                print(f"DEBUG: Error in OpenAlex search: {e}")
                break
    
    return records


async def fetch_all_sources_async(
    pubmed_query: str,
    openalex_query: str,
    max_results: Optional[int] = None
) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch from both sources concurrently.
    
    Returns:
        Tuple of (pubmed_records, openalex_records)
    """
    pubmed_task = fetch_pubmed_async(pubmed_query, max_results)
    openalex_task = fetch_openalex_async(openalex_query, max_results)
    
    pubmed_records, openalex_records = await asyncio.gather(
        pubmed_task,
        openalex_task,
        return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(pubmed_records, Exception):
        print(f"ERROR: PubMed fetch failed: {pubmed_records}")
        pubmed_records = []
    if isinstance(openalex_records, Exception):
        print(f"ERROR: OpenAlex fetch failed: {openalex_records}")
        openalex_records = []
    
    return pubmed_records, openalex_records


def normalize_document(record: Dict, source: str) -> Dict:
    """
    Normalize a document record to internal format.
    
    Args:
        record: Document record from API
        source: Source name ('pubmed' or 'openalex')
    
    Returns:
        Normalized document dict
    """
    # Already normalized if from our fetch functions, but ensure consistency
    normalized = {
        "pmid": record.get("pmid"),
        "pmcid": record.get("pmcid"),
        "title": record.get("title", ""),
        "abstract": record.get("abstract", ""),
        "authors": record.get("authors"),
        "year": record.get("year"),
        "journal": record.get("journal") or record.get("venue"),
        "volume": record.get("volume"),
        "issue": record.get("issue"),
        "doi": record.get("doi"),
        "pubmed_url": record.get("pubmed_url"),
        "doi_url": record.get("doi_url"),
        "url": record.get("url") or record.get("doi_url") or record.get("pubmed_url"),
        "citations_crossref": record.get("citations_crossref"),
        "source": source,
    }
    
    return normalized


def deduplicate_documents(documents: List[Dict]) -> List[Dict]:
    """
    Deduplicate documents using DOI as primary key, then fingerprint.
    
    Args:
        documents: List of document dicts
    
    Returns:
        Deduplicated list
    """
    seen_dois = set()
    seen_pmids = set()
    seen_pmcids = set()
    seen_fingerprints = set()
    deduplicated = []
    
    from db.repository import _fingerprint, _first_author
    
    for doc in documents:
        # Primary: DOI
        doi = doc.get("doi")
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)
        
        # Secondary: PMID
        pmid = doc.get("pmid")
        if pmid and pmid in seen_pmids:
            continue
        if pmid:
            seen_pmids.add(pmid)
        
        # Tertiary: PMCID
        pmcid = doc.get("pmcid")
        if pmcid and pmcid in seen_pmcids:
            continue
        if pmcid:
            seen_pmcids.add(pmcid)
        
        # Fallback: fingerprint (title + year + first_author)
        title = doc.get("title", "")
        year = doc.get("year")
        authors = doc.get("authors")
        first_author = _first_author(authors)
        fingerprint = _fingerprint(title, year, first_author)
        
        if fingerprint and fingerprint in seen_fingerprints:
            continue
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        
        deduplicated.append(doc)
    
    return deduplicated


def generate_corpus(
    project_id: int,
    pubmed_query: str,
    openalex_query: str,
    max_results: Optional[int] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Generate corpus for a review by fetching from PubMed and OpenAlex.
    
    Uses server-side config limits (MAX_PUBMED_RESULTS_PER_REVIEW, MAX_OPENALEX_RESULTS_PER_REVIEW).
    The max_results parameter is ignored in favor of config values.
    
    Args:
        project_id: Project ID
        pubmed_query: PubMed search query
        openalex_query: OpenAlex search query
        max_results: Ignored - uses config limits instead
        api_key: Not used, kept for API compatibility
    
    Returns:
        Dict with counts: pubmed_count, openalex_count, total_unique, inserted_count
    """
    from db.connection import connect
    from db.repository import bulk_insert_unscreened, save_ingestion_log
    
    # Use config limits, not user-provided max_results
    pubmed_limit = config.MAX_PUBMED_RESULTS_PER_REVIEW
    openalex_limit = config.MAX_OPENALEX_RESULTS_PER_REVIEW
    
    # Run async fetch with config limits
    # Handle event loop properly for Flask threading
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # No event loop in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Fetch from both sources with their respective limits
        pubmed_task = fetch_pubmed_async(pubmed_query, pubmed_limit)
        openalex_task = fetch_openalex_async(openalex_query, openalex_limit)
        
        pubmed_records, openalex_records = loop.run_until_complete(
            asyncio.gather(pubmed_task, openalex_task, return_exceptions=True)
        )
        
        # Handle exceptions
        if isinstance(pubmed_records, Exception):
            print(f"ERROR: PubMed fetch failed: {pubmed_records}")
            pubmed_records = []
        if isinstance(openalex_records, Exception):
            print(f"ERROR: OpenAlex fetch failed: {openalex_records}")
            openalex_records = []
    finally:
        # Only close if we created a new loop
        try:
            current_loop = asyncio.get_event_loop()
            if current_loop == loop and not current_loop.is_closed():
                # Only close if it's our loop and not already closed
                loop.close()
        except RuntimeError:
            pass  # Loop already closed or doesn't exist
    
    # Normalize all records
    all_records = []
    for record in pubmed_records:
        normalized = normalize_document(record, "pubmed")
        all_records.append(normalized)
    
    for record in openalex_records:
        normalized = normalize_document(record, "openalex")
        all_records.append(normalized)
    
    # Track counts before deduplication
    pubmed_fetched = len(pubmed_records)
    openalex_fetched = len(openalex_records)
    
    # Deduplicate (removes cross-source duplicates)
    deduplicated = deduplicate_documents(all_records)
    
    # Count unique per source after deduplication (for reporting)
    pubmed_unique = sum(1 for doc in deduplicated if doc.get("source") == "pubmed")
    openalex_unique = sum(1 for doc in deduplicated if doc.get("source") == "openalex")
    
    # Store in database
    with connect() as con:
        inserted_count = bulk_insert_unscreened(con, project_id, deduplicated)
        con.commit()
        
        # Save ingestion log
        log_data = {
            "pubmed_query": pubmed_query,
            "openalex_query": openalex_query,
            "pubmed_count": pubmed_fetched,
            "openalex_count": openalex_fetched,
            "total_unique": len(deduplicated),
        }
        save_ingestion_log(con, project_id, log_data)
        con.commit()
    
    return {
        "pubmed_count": pubmed_fetched,
        "pubmed_unique": pubmed_unique,
        "openalex_count": openalex_fetched,
        "openalex_unique": openalex_unique,
        "total_unique": len(deduplicated),
        "inserted_count": inserted_count,
    }

