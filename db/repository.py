import sqlite3, hashlib
from typing import Optional, Dict, List
import pandas as pd
import json
from datetime import datetime

# ---------- utilities ----------
def _first_author(authors: Optional[str]) -> Optional[str]:
    if not isinstance(authors, str) or not authors.strip():
        return None
    # prefer split by ';' (common in PubMed), else fall back to ','
    chunk = authors.split(';')[0] if ';' in authors else authors.split(',')[0]
    return chunk.strip() or None

def _fingerprint(title: str, year: Optional[int], first_author: Optional[str]) -> str:
    t = (title or "").strip().lower()
    y = str(year or "")
    a = (first_author or "").strip().lower() if first_author else ""
    return hashlib.sha256(f"{t}::{y}::{a}".encode()).hexdigest()

# ---------- projects ----------
def get_or_create_project(con: sqlite3.Connection, name: str) -> int:
    cur = con.execute("SELECT id FROM projects WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = con.execute("INSERT INTO projects (name) VALUES (?)", (name,))
    return cur.lastrowid

# ---------- upsert paper (include/maybe) ----------
# SECURITY NOTE: cols is a static allowlist defined here, never derived from user input.
# The f-string interpolation of column names is safe because it only joins these literals.
_PAPER_COLS = (
    "project_id", "pmid", "pmcid", "doi", "title", "abstract", "authors", "year",
    "venue", "volume", "issue", "pubmed_url", "doi_url", "url", "pdf_path",
    "status", "score", "rationale", "citations_crossref", "fingerprint",
)

def upsert_paper(con: sqlite3.Connection, project_id: int, paper: Dict) -> int:
    cols = list(_PAPER_COLS)
    vals = [project_id] + [paper.get(k) for k in cols[1:]]

    # Insert if new (unique constraints on doi/pmid/pmcid/fingerprint)
    con.execute(f"""
        INSERT OR IGNORE INTO papers
        ({", ".join(cols)})
        VALUES ({", ".join(["?"]*len(cols))})
    """, vals)

    # Update if exists; promote status to 'include' if new says so
    # Preserve existing authors if new data doesn't have authors
    con.execute("""
        UPDATE papers
           SET title      = COALESCE(?, title),
               abstract   = COALESCE(?, abstract),
               authors    = CASE 
                              WHEN ? IS NOT NULL AND ? != '' THEN ?
                              ELSE authors
                            END,
               year       = COALESCE(?, year),
               venue      = COALESCE(?, venue),
               volume     = COALESCE(?, volume),
               issue      = COALESCE(?, issue),
               pubmed_url = COALESCE(?, pubmed_url),
               doi_url    = COALESCE(?, doi_url),
               url        = COALESCE(?, url),
               pdf_path   = COALESCE(?, pdf_path),
               status     = CASE 
                              WHEN ? = 'include' THEN 'include'
                              WHEN ? = 'UNSCREENED' AND status IN ('include', 'maybe') THEN status
                              WHEN ? = 'UNSCREENED' THEN 'UNSCREENED'
                              ELSE COALESCE(?, status)
                            END,
               score      = COALESCE(?, score),
               rationale  = COALESCE(?, rationale),
               citations_crossref = COALESCE(?, citations_crossref)
         WHERE project_id = ?
           AND (
                 (doi  IS NOT NULL AND doi  = ?)
              OR (pmid IS NOT NULL AND pmid = ?)
              OR (pmcid IS NOT NULL AND pmcid = ?)
              OR (fingerprint IS NOT NULL AND fingerprint = ?)
           )
    """, [
        paper.get("title"),
        paper.get("abstract"),
        paper.get("authors"),  # For CASE check
        paper.get("authors"),  # For CASE check
        paper.get("authors"),  # For CASE assignment
        paper.get("year"),
        paper.get("venue"),
        paper.get("volume"),
        paper.get("issue"),
        paper.get("pubmed_url"),
        paper.get("doi_url"),
        paper.get("url"),
        paper.get("pdf_path"),
        paper.get("status"),  # First status param for 'include' check
        paper.get("status"),  # Second status param for 'UNSCREENED' check
        paper.get("status"),  # Third status param for 'UNSCREENED' assignment
        paper.get("status"),  # Fourth status param for COALESCE
        paper.get("score"),
        paper.get("rationale"),
        paper.get("citations_crossref"),
        project_id,
        paper.get("doi"),
        paper.get("pmid"),
        paper.get("pmcid"),
        paper.get("fingerprint"),
    ])

    # Fetch id
    cur = con.execute("""
        SELECT id FROM papers
         WHERE project_id = ?
           AND (
                 (doi  IS NOT NULL AND doi  = ?)
              OR (pmid IS NOT NULL AND pmid = ?)
              OR (pmcid IS NOT NULL AND pmcid = ?)
              OR (fingerprint IS NOT NULL AND fingerprint = ?)
           )
    """, (project_id, paper.get("doi"), paper.get("pmid"), paper.get("pmcid"), paper.get("fingerprint")))
    row = cur.fetchone()
    if row is None:
        # If no paper found, it means the INSERT OR IGNORE didn't work due to constraints
        # or the paper wasn't inserted for some reason. Let's try to insert it again.
        con.execute(f"""
            INSERT INTO papers
            ({", ".join(cols)})
            VALUES ({", ".join(["?"]*len(cols))})
        """, vals)
        paper_id = con.lastrowid
    else:
        paper_id = row[0]

    # Mirror into FTS (use INSERT OR REPLACE since FTS5 doesn't support DELETE)
    con.execute("INSERT OR REPLACE INTO papers_fts(rowid, title, abstract) VALUES (?,?,?)",
                (paper_id, paper.get("title"), paper.get("abstract")))
    return paper_id

# ---------- bulk ingest from your df/df_results ----------
def bulk_ingest_from_dfs(
    con: sqlite3.Connection,
    project_id: int,
    df: pd.DataFrame,
    df_results: pd.DataFrame
):
    assert {"decision","score"}.issubset(df_results.columns), "df_results must include decision & score"
    keep = df_results["decision"].isin(["include","maybe"])
    df_k = df.loc[keep].reset_index(drop=True)
    df_r = df_results.loc[keep].reset_index(drop=True)
    

    for i, row in df_k.iterrows():
        try:
            dec = df_r.loc[i, "decision"]
            score = int(df_r.loc[i, "score"]) if pd.notna(df_r.loc[i, "score"]) else None
            rationale = None
            if "rationale" in df_r.columns and pd.notna(df_r.loc[i, "rationale"]):
                rationale = str(df_r.loc[i, "rationale"])

            title = row.get("title")
            abstract = row.get("abstract")
            authors = row.get("authors")
            year = int(row["year"]) if "year" in row and pd.notna(row["year"]) else None
            first_author = _first_author(authors)

            pmid = str(row["pmid"]) if "pmid" in row and pd.notna(row["pmid"]) else None
            pmcid = str(row["pmcid"]) if "pmcid" in row and pd.notna(row["pmcid"]) else None
            doi = str(row["doi"]) if "doi" in row and pd.notna(row["doi"]) else None

            pubmed_url = row.get("pubmed_url")
            doi_url    = row.get("doi_url")
            openalex_url = row.get("openalex_url")
            semantic_scholar_url = row.get("semantic_scholar_url")
            # Use best available URL (prefer DOI > PubMed > OpenAlex > Semantic Scholar)
            url        = doi_url or pubmed_url or openalex_url or semantic_scholar_url
        except Exception as e:
            print(f"DEBUG: Error processing row {i}: {e}")
            print(f"DEBUG: Row data: {dict(row)}")
            print(f"DEBUG: Decision data: {df_r.loc[i].to_dict() if i < len(df_r) else 'Index out of range'}")
            raise

        paper = {
            # ids
            "pmid": pmid,
            "pmcid": pmcid,
            "doi": doi,
            # content
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "year": year,
            "venue": row.get("journal"),     # map 'journal' -> 'venue'
            "volume": str(row["volume"]) if "volume" in row and pd.notna(row["volume"]) else None,
            "issue": str(row["issue"]) if "issue" in row and pd.notna(row["issue"]) else None,
            # links
            "pubmed_url": pubmed_url,
            "doi_url": doi_url,
            "url": url,
            "pdf_path": None,
            # screening
            "status": dec,                   # 'include' | 'maybe'
            "score": score,
            "rationale": rationale,
            # other
            "citations_crossref": int(row["citations_crossref"]) if "citations_crossref" in row and pd.notna(row["citations_crossref"]) and row["citations_crossref"] is not None else None,
            "fingerprint": _fingerprint(title or "", year, first_author),
        }
        
        upsert_paper(con, project_id, paper)

# ---------- queries for GUI ----------
def list_included(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, abstract, authors, year, venue, doi, pmid, pmcid,
               doi_url, pubmed_url, url, pdf_path, status, score, rationale, citations_crossref, project_id
          FROM papers
         WHERE project_id = ? AND status = 'include'
      ORDER BY COALESCE(score,0) DESC, year DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def list_maybe(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, abstract, authors, year, venue, doi, pmid, pmcid,
               doi_url, pubmed_url, url, pdf_path, status, score, rationale, citations_crossref, project_id
          FROM papers
         WHERE project_id = ? AND status = 'maybe'
      ORDER BY COALESCE(score,0) DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def set_status(con: sqlite3.Connection, paper_id: int, new_status: str, score: Optional[int] = None, rationale: Optional[str] = None):
    assert new_status in ("include","maybe","UNSCREENED")
    con.execute("""
        UPDATE papers
           SET status = ?,
               score = COALESCE(?, score),
               rationale = COALESCE(?, rationale)
         WHERE id = ?
    """, (new_status, score, rationale, paper_id))

# ---------- PICO functions ----------
def save_pico(con: sqlite3.Connection, project_id: int, pico) -> int:
    """Save or update PICO for a project. Returns pico id."""
    from agents.pico import PICO
    
    # Serialize extra_terms to JSON
    extra_terms_json = None
    if pico.extra_terms:
        extra_terms_json = json.dumps(pico.extra_terms)
    
    now = datetime.utcnow().isoformat()
    
    # Insert or replace
    con.execute("""
        INSERT OR REPLACE INTO pico 
        (project_id, population, intervention, comparison, outcome, study_design, extra_terms, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT created_at FROM pico WHERE project_id = ?), ?),
                ?)
    """, (
        project_id,
        pico.population,
        pico.intervention,
        pico.comparison,
        pico.outcome,
        pico.study_design,
        extra_terms_json,
        project_id,
        now,
        now
    ))
    
    # Get id
    cur = con.execute("SELECT id FROM pico WHERE project_id = ?", (project_id,))
    row = cur.fetchone()
    return row[0] if row else con.lastrowid

def get_pico(con: sqlite3.Connection, project_id: int):
    """Get PICO for a project. Returns PICO object or None."""
    from agents.pico import PICO
    
    cur = con.execute("""
        SELECT population, intervention, comparison, outcome, study_design, extra_terms
        FROM pico
        WHERE project_id = ?
    """, (project_id,))
    
    row = cur.fetchone()
    if not row:
        return None
    
    # Parse extra_terms JSON
    extra_terms = None
    if row[5]:
        try:
            extra_terms = json.loads(row[5])
        except (json.JSONDecodeError, TypeError):
            pass
    
    return PICO(
        population=row[0],
        intervention=row[1],
        comparison=row[2],
        outcome=row[3],
        study_design=row[4],
        extra_terms=extra_terms
    )

def save_pico_expansion(con: sqlite3.Connection, project_id: int, expansion: Dict) -> int:
    """Save or update PICO expansion results. Returns expansion id."""
    now = datetime.utcnow().isoformat()
    
    # Serialize pico_keywords to JSON
    pico_keywords_json = json.dumps(expansion.get("pico_keywords", {}))
    
    con.execute("""
        INSERT OR REPLACE INTO pico_expansions
        (project_id, question_summary, pubmed_query, openalex_query, pico_keywords, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        expansion.get("question_summary", ""),
        expansion.get("pubmed_query", ""),
        expansion.get("openalex_query", ""),
        pico_keywords_json,
        now
    ))
    
    # Get id
    cur = con.execute("SELECT id FROM pico_expansions WHERE project_id = ?", (project_id,))
    row = cur.fetchone()
    return row[0] if row else con.lastrowid

def get_pico_expansion(con: sqlite3.Connection, project_id: int) -> Optional[Dict]:
    """Get PICO expansion for a project. Returns dict or None."""
    cur = con.execute("""
        SELECT question_summary, pubmed_query, openalex_query, pico_keywords, created_at
        FROM pico_expansions
        WHERE project_id = ?
    """, (project_id,))
    
    row = cur.fetchone()
    if not row:
        return None
    
    # Parse pico_keywords JSON
    pico_keywords = {}
    if row[3]:
        try:
            pico_keywords = json.loads(row[3])
        except (json.JSONDecodeError, TypeError):
            pass
    
    return {
        "question_summary": row[0],
        "pubmed_query": row[1],
        "openalex_query": row[2],
        "pico_keywords": pico_keywords,
        "created_at": row[4]
    }

# ---------- corpus generation functions ----------
def bulk_insert_unscreened(con: sqlite3.Connection, project_id: int, documents: List[Dict]) -> int:
    """Bulk insert documents with UNSCREENED status. Returns count inserted."""
    count = 0
    errors = 0
    
    # Check existing papers count before insertion
    cur = con.execute("SELECT COUNT(*) FROM papers WHERE project_id = ?", (project_id,))
    existing_count_before = cur.fetchone()[0]
    
    for doc in documents:
        # Calculate fingerprint
        title = doc.get("title") or ""
        year = doc.get("year")
        authors = doc.get("authors")
        first_author = _first_author(authors)
        fingerprint = _fingerprint(title, year, first_author)
        
        paper = {
            "pmid": doc.get("pmid"),
            "pmcid": doc.get("pmcid"),
            "doi": doc.get("doi"),
            "title": title,
            "abstract": doc.get("abstract"),
            "authors": authors,
            "year": year,
            "venue": doc.get("journal") or doc.get("venue"),
            "volume": doc.get("volume"),
            "issue": doc.get("issue"),
            "pubmed_url": doc.get("pubmed_url"),
            "doi_url": doc.get("doi_url"),
            "url": doc.get("url"),
            "pdf_path": None,
            "status": "UNSCREENED",
            "score": None,
            "rationale": None,
            "citations_crossref": doc.get("citations_crossref"),
            "fingerprint": fingerprint,
        }
        
        try:
            upsert_paper(con, project_id, paper)
            count += 1
        except Exception as e:
            errors += 1
            # Log error but continue - might be duplicate constraint
            if errors <= 5:  # Log first 5 errors to avoid spam
                title_str = title[:50] if title else "None"
                print(f"DEBUG: Error inserting paper '{title_str}...': {e}", flush=True)
            # Check if paper already exists (might be a duplicate)
            # If it's a constraint violation, that's okay - paper already exists
            if "UNIQUE constraint" not in str(e) and "constraint" not in str(e).lower():
                # Only print non-constraint errors
                if errors <= 5:
                    import traceback
                    traceback.print_exc()
            continue
    
    # Check actual inserted count (upsert_paper uses INSERT OR IGNORE, so some may not actually insert)
    cur = con.execute("SELECT COUNT(*) FROM papers WHERE project_id = ?", (project_id,))
    existing_count_after = cur.fetchone()[0]
    actually_inserted = existing_count_after - existing_count_before
    
    if actually_inserted < count or errors > 0:
        print(f"DEBUG: Database insertion: attempted {len(documents)}, processed {count}, "
              f"errors {errors}, actually inserted {actually_inserted} new papers", flush=True)
    
    return count

def save_ingestion_log(con: sqlite3.Connection, project_id: int, log_data: Dict) -> int:
    """Save ingestion log entry. Returns log id."""
    now = datetime.utcnow().isoformat()
    
    cur = con.execute("""
        INSERT INTO review_ingestion_logs
        (project_id, pubmed_query, openalex_query, pubmed_count, openalex_count, total_unique, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        log_data.get("pubmed_query"),
        log_data.get("openalex_query"),
        log_data.get("pubmed_count", 0),
        log_data.get("openalex_count", 0),
        log_data.get("total_unique", 0),
        now
    ))
    
    return cur.lastrowid

# ---------- screening labels functions ----------
def get_labeled_papers(con: sqlite3.Connection, project_id: int) -> List[Dict]:
    """Get all papers that have been labeled for screening. Returns list of dicts with paper_id, title, abstract, label."""
    cur = con.execute("""
        SELECT p.id as paper_id, p.title, p.abstract, sl.label
        FROM papers p
        INNER JOIN screening_labels sl ON p.id = sl.paper_id
        WHERE p.project_id = ? AND sl.project_id = ?
        ORDER BY sl.timestamp DESC
    """, (project_id, project_id))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def get_unlabeled_papers(con: sqlite3.Connection, project_id: int, limit: Optional[int] = None) -> List[Dict]:
    """Get papers that have not been labeled yet. Returns list of dicts with paper_id, title, abstract, venue, year."""
    query = """
        SELECT p.id as paper_id, p.title, p.abstract, p.venue, p.year
        FROM papers p
        LEFT JOIN screening_labels sl ON p.id = sl.paper_id AND sl.project_id = ?
        WHERE p.project_id = ? AND sl.id IS NULL
        ORDER BY p.added_at DESC
    """
    if limit is not None:
        query += f" LIMIT {limit}"
    
    cur = con.execute(query, (project_id, project_id))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def get_included_papers(con: sqlite3.Connection, project_id: int) -> List[Dict]:
    """
    Get all papers labeled as INCLUDE for a project.
    
    Returns:
        List of dicts with paper details: id, title, abstract, year, venue, authors, etc.
    """
    query = """
        SELECT 
            p.id as paper_id,
            p.title,
            p.abstract,
            p.year,
            p.venue,
            p.authors,
            p.pmid,
            p.pmcid,
            p.doi,
            p.url,
            p.pubmed_url,
            p.doi_url,
            p.status,
            p.score,
            p.rationale,
            p.added_at
        FROM papers p
        INNER JOIN screening_labels sl ON p.id = sl.paper_id AND sl.project_id = ?
        WHERE sl.label = 'INCLUDE'
        ORDER BY p.added_at DESC
    """
    
    cur = con.execute(query, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def save_screening_labels(con: sqlite3.Connection, project_id: int, labels: Dict[int, str]) -> Dict[str, int]:
    """
    Save screening labels for papers. Updates both screening_labels table and papers.status.
    
    Args:
        con: Database connection
        project_id: Project ID
        labels: Dict mapping paper_id -> label ("INCLUDE" or "EXCLUDE")
    
    Returns:
        Dict with 'saved' (number of labels saved) and 'updated_papers' (number of papers status updated)
    """
    now = datetime.utcnow().isoformat()
    saved = 0
    updated_papers = 0
    
    for paper_id, label in labels.items():
        # Validate label
        if label not in ("INCLUDE", "EXCLUDE"):
            continue
        
        # Insert or replace label (handles UNIQUE constraint)
        con.execute("""
            INSERT OR REPLACE INTO screening_labels (project_id, paper_id, label, timestamp)
            VALUES (?, ?, ?, ?)
        """, (project_id, paper_id, label, now))
        saved += 1
        
        # Update papers.status
        # INCLUDE -> 'include', EXCLUDE -> 'excluded'
        new_status = "include" if label == "INCLUDE" else "excluded"
        cur = con.execute("""
            UPDATE papers
            SET status = ?
            WHERE id = ? AND project_id = ?
        """, (new_status, paper_id, project_id))
        
        if cur.rowcount > 0:
            updated_papers += 1
    
    return {"saved": saved, "updated_papers": updated_papers}

def get_screening_stats(con: sqlite3.Connection, project_id: int) -> Dict[str, int]:
    """
    Get screening statistics for a project.
    
    Returns:
        Dict with total_papers, labeled_count, unlabeled_count, included_count, excluded_count
    """
    # Get total papers count
    cur = con.execute("SELECT COUNT(*) FROM papers WHERE project_id = ?", (project_id,))
    total_papers = cur.fetchone()[0]
    
    # Get labeled papers count
    cur = con.execute("""
        SELECT COUNT(DISTINCT sl.paper_id)
        FROM screening_labels sl
        WHERE sl.project_id = ?
    """, (project_id,))
    labeled_count = cur.fetchone()[0]
    
    # Get included/excluded counts
    cur = con.execute("""
        SELECT 
            SUM(CASE WHEN sl.label = 'INCLUDE' THEN 1 ELSE 0 END) as included_count,
            SUM(CASE WHEN sl.label = 'EXCLUDE' THEN 1 ELSE 0 END) as excluded_count
        FROM screening_labels sl
        WHERE sl.project_id = ?
    """, (project_id,))
    row = cur.fetchone()
    included_count = row[0] if row[0] else 0
    excluded_count = row[1] if row[1] else 0
    
    unlabeled_count = total_papers - labeled_count
    
    # Get last batch timestamp
    cur = con.execute("""
        SELECT MAX(sl.timestamp) as last_batch_timestamp
        FROM screening_labels sl
        WHERE sl.project_id = ?
    """, (project_id,))
    row = cur.fetchone()
    last_batch_timestamp = row[0] if row and row[0] else None
    
    # Estimate recent batches (optional - simplified)
    n_recent_batches = 0  # Can be enhanced later if needed
    
    return {
        "n_total_corpus": total_papers,
        "n_labeled": labeled_count,
        "n_unlabeled": unlabeled_count,
        "n_included": included_count,
        "n_excluded": excluded_count,
        "n_recent_batches": n_recent_batches,
        "last_batch_timestamp": last_batch_timestamp
    }

def get_recent_batch_statistics(con: sqlite3.Connection, project_id: int, batch_count: int = 5) -> Dict:
    """
    Get statistics for the most recent batches to detect low yield.
    
    Args:
        con: Database connection
        project_id: Project ID
        batch_count: Number of recent batches to analyze
    
    Returns:
        Dict with include_rate, total_papers_in_batches, included_in_batches
    """
    # Get most recent batch timestamps (assuming batches are submitted at once)
    # We'll look at papers labeled in the most recent time periods
    cur = con.execute("""
        SELECT sl.label, sl.timestamp
        FROM screening_labels sl
        WHERE sl.project_id = ?
        ORDER BY sl.timestamp DESC
        LIMIT ?
    """, (project_id, batch_count * 20))  # Assume up to 20 papers per batch
    
    rows = cur.fetchall()
    if not rows:
        return {"include_rate": 0.0, "total_papers_in_batches": 0, "included_in_batches": 0}
    
    # Count includes in recent papers
    total = len(rows)
    included = sum(1 for row in rows if row[0] == "INCLUDE")
    include_rate = included / total if total > 0 else 0.0
    
    return {
        "include_rate": include_rate,
        "total_papers_in_batches": total,
        "included_in_batches": included
    }

def save_agent_summary(
    con: sqlite3.Connection,
    project_id: int,
    paper_id: int,
    summary_data: Dict
) -> int:
    """
    Save or update an agent summary for a paper.
    
    Args:
        con: Database connection
        project_id: Project ID
        paper_id: Paper ID
        summary_data: Dict with keys: population, intervention, comparator, outcomes, 
                     main_findings, sample_size, notes
    
    Returns:
        ID of saved summary
    """
    now = datetime.utcnow().isoformat()
    
    # Insert or replace summary
    cur = con.execute("""
        INSERT OR REPLACE INTO agent_summaries 
        (project_id, paper_id, population, intervention, comparator, outcomes, 
         main_findings, sample_size, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        paper_id,
        summary_data.get("population"),
        summary_data.get("intervention"),
        summary_data.get("comparator"),
        summary_data.get("outcomes"),
        summary_data.get("main_findings"),
        summary_data.get("sample_size"),
        summary_data.get("notes"),
        now
    ))
    
    return cur.lastrowid


def save_project_overview(
    con: sqlite3.Connection,
    project_id: int,
    overview_json: Dict
) -> int:
    """
    Save or update project agent overview.
    
    Args:
        con: Database connection
        project_id: Project ID
        overview_json: Dict containing overview data
    
    Returns:
        ID of saved overview
    """
    now = datetime.utcnow().isoformat()
    overview_text = json.dumps(overview_json)
    
    # Insert or replace overview
    cur = con.execute("""
        INSERT OR REPLACE INTO project_agent_overview 
        (project_id, overview_json, created_at)
        VALUES (?, ?, ?)
    """, (project_id, overview_text, now))
    
    return cur.lastrowid


def get_agent_summaries(con: sqlite3.Connection, project_id: int) -> List[Dict]:
    """
    Get all agent summaries for a project.
    
    Args:
        con: Database connection
        project_id: Project ID
    
    Returns:
        List of dicts with summary data and paper info
    """
    query = """
        SELECT 
            a.id as summary_id,
            a.project_id,
            a.paper_id,
            a.population,
            a.intervention,
            a.comparator,
            a.outcomes,
            a.main_findings,
            a.sample_size,
            a.notes,
            a.created_at,
            p.title,
            p.abstract,
            p.year,
            p.venue,
            p.authors
        FROM agent_summaries a
        INNER JOIN papers p ON a.paper_id = p.id
        WHERE a.project_id = ?
        ORDER BY a.created_at DESC
    """
    
    cur = con.execute(query, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_project_overview(con: sqlite3.Connection, project_id: int) -> Optional[Dict]:
    """
    Get project agent overview if it exists.
    
    Args:
        con: Database connection
        project_id: Project ID
    
    Returns:
        Dict with overview data or None
    """
    cur = con.execute("""
        SELECT overview_json, created_at
        FROM project_agent_overview
        WHERE project_id = ?
    """, (project_id,))
    
    row = cur.fetchone()
    if row:
        overview_json_text = row[0]
        try:
            return json.loads(overview_json_text)
        except json.JSONDecodeError:
            return None
    return None

