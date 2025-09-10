import sqlite3, hashlib
from typing import Optional, Dict, List
import pandas as pd

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
def upsert_paper(con: sqlite3.Connection, project_id: int, paper: Dict) -> int:
    cols = [
        "project_id", "pmid", "pmcid", "doi", "title", "abstract", "authors", "year",
        "venue", "volume", "issue", "pubmed_url", "doi_url", "url", "pdf_path",
        "status", "score", "rationale", "citations_crossref", "fingerprint"
    ]
    vals = [project_id] + [paper.get(k) for k in cols[1:]]

    # Insert if new (unique constraints on doi/pmid/pmcid/fingerprint)
    con.execute(f"""
        INSERT OR IGNORE INTO papers
        ({", ".join(cols)})
        VALUES ({", ".join(["?"]*len(cols))})
    """, vals)

    # Update if exists; promote status to 'include' if new says so
    con.execute("""
        UPDATE papers
           SET title      = COALESCE(?, title),
               abstract   = COALESCE(?, abstract),
               authors    = COALESCE(?, authors),
               year       = COALESCE(?, year),
               venue      = COALESCE(?, venue),
               volume     = COALESCE(?, volume),
               issue      = COALESCE(?, issue),
               pubmed_url = COALESCE(?, pubmed_url),
               doi_url    = COALESCE(?, doi_url),
               url        = COALESCE(?, url),
               pdf_path   = COALESCE(?, pdf_path),
               status     = CASE WHEN ? = 'include' THEN 'include' ELSE status END,
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
        paper.get("authors"),
        paper.get("year"),
        paper.get("venue"),
        paper.get("volume"),
        paper.get("issue"),
        paper.get("pubmed_url"),
        paper.get("doi_url"),
        paper.get("url"),
        paper.get("pdf_path"),
        paper.get("status"),
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
    paper_id = cur.fetchone()[0]

    # Mirror into FTS
    con.execute("DELETE FROM papers_fts WHERE rowid = ?", (paper_id,))
    con.execute("INSERT INTO papers_fts(rowid, title, abstract) VALUES (?,?,?)",
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
        url        = doi_url or pubmed_url

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
            "citations_crossref": int(row["citations_crossref"]) if "citations_crossref" in row and pd.notna(row["citations_crossref"]) else None,
            "fingerprint": _fingerprint(title or "", year, first_author),
        }
        upsert_paper(con, project_id, paper)

# ---------- queries for GUI ----------
def list_included(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, authors, year, venue, doi, pmid, pmcid,
               doi_url, pubmed_url, url, pdf_path, score, rationale, citations_crossref
          FROM papers
         WHERE project_id = ? AND status = 'include'
      ORDER BY COALESCE(score,0) DESC, year DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def list_maybe(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, authors, year, venue, doi, pmid, pmcid,
               doi_url, pubmed_url, url, pdf_path, score, rationale, citations_crossref
          FROM papers
         WHERE project_id = ? AND status = 'maybe'
      ORDER BY COALESCE(score,0) DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def set_status(con: sqlite3.Connection, paper_id: int, new_status: str, score: Optional[int] = None, rationale: Optional[str] = None):
    assert new_status in ("include","maybe")
    con.execute("""
        UPDATE papers
           SET status = ?,
               score = COALESCE(?, score),
               rationale = COALESCE(?, rationale)
         WHERE id = ?
    """, (new_status, score, rationale, paper_id))

