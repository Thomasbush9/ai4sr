import sqlite3, hashlib
from typing import Optional, Dict, List
import pandas as pd

# ---------- utils ----------
def _fingerprint(title: str, year: Optional[int], first_author: Optional[str]) -> str:
    t = (title or "").strip().lower()
    y = str(year or "")
    a = (first_author or "").strip().lower()
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
    cols = ["project_id","source_id","doi","title","abstract","authors","year",
            "venue","url","pdf_path","status","score","fingerprint"]
    vals = [project_id] + [paper.get(k) for k in cols[1:]]

    con.execute("""
        INSERT OR IGNORE INTO papers
        (project_id, source_id, doi, title, abstract, authors, year, venue, url, pdf_path, status, score, fingerprint)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, vals)

    con.execute("""
        UPDATE papers
           SET title      = COALESCE(?, title),
               abstract   = COALESCE(?, abstract),
               authors    = COALESCE(?, authors),
               year       = COALESCE(?, year),
               venue      = COALESCE(?, venue),
               url        = COALESCE(?, url),
               pdf_path   = COALESCE(?, pdf_path),
               status     = CASE WHEN ? = 'include' THEN 'include' ELSE status END,
               score      = COALESCE(?, score)
         WHERE project_id = ?
           AND (
               (doi IS NOT NULL AND doi = ?)
            OR (source_id IS NOT NULL AND source_id = ?)
            OR (fingerprint IS NOT NULL AND fingerprint = ?)
           )
    """, [
        paper.get("title"),
        paper.get("abstract"),
        paper.get("authors"),
        paper.get("year"),
        paper.get("venue"),
        paper.get("url"),
        paper.get("pdf_path"),
        paper.get("status"),
        paper.get("score"),
        project_id,
        paper.get("doi"),
        paper.get("source_id"),
        paper.get("fingerprint"),
    ])

    cur = con.execute("""
        SELECT id FROM papers
        WHERE project_id = ?
          AND (
               (doi IS NOT NULL AND doi = ?)
            OR (source_id IS NOT NULL AND source_id = ?)
            OR (fingerprint IS NOT NULL AND fingerprint = ?)
          )
    """, (project_id, paper.get("doi"), paper.get("source_id"), paper.get("fingerprint")))
    paper_id = cur.fetchone()[0]

    # Keep FTS in sync (simple)
    con.execute("DELETE FROM papers_fts WHERE rowid = ?", (paper_id,))
    con.execute("INSERT INTO papers_fts(rowid, title, abstract) VALUES (?,?,?)",
                (paper_id, paper.get("title"), paper.get("abstract")))
    return paper_id

def bulk_ingest_from_dfs(con: sqlite3.Connection, project_id: int, df: pd.DataFrame, df_results: pd.DataFrame):
    assert {"decision","score"}.issubset(df_results.columns), "df_results must have decision & score"

    keep = df_results["decision"].isin(["include","maybe"])
    df_k = df.loc[keep].reset_index(drop=True)
    df_r = df_results.loc[keep].reset_index(drop=True)

    for i, row in df_k.iterrows():
        dec = df_r.loc[i, "decision"]
        sc  = int(df_r.loc[i, "score"]) if pd.notna(df_r.loc[i, "score"]) else None

        title = row.get("title")
        abstract = row.get("abstract")
        authors = row.get("authors")
        year = int(row["year"]) if "year" in row and pd.notna(row["year"]) else None
        first_author = None
        if isinstance(authors, str) and authors.strip():
            first_author = authors.split(",")[0]

        paper = {
            "source_id": row.get("source_id"),
            "doi": row.get("doi"),
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "year": year,
            "venue": row.get("venue"),
            "url": row.get("url"),
            "pdf_path": None,
            "status": dec,               # 'include' | 'maybe'
            "score": sc,
            "fingerprint": _fingerprint(title or "", year, first_author),
        }
        upsert_paper(con, project_id, paper)

# ---------- queries for GUI ----------
def list_included(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, authors, year, venue, url, pdf_path, score
          FROM papers
         WHERE project_id = ? AND status = 'include'
      ORDER BY COALESCE(score,0) DESC, year DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def list_maybe(con: sqlite3.Connection, project_id: int) -> List[dict]:
    cur = con.execute("""
        SELECT id, title, authors, year, venue, url, pdf_path, score
          FROM papers
         WHERE project_id = ? AND status = 'maybe'
      ORDER BY COALESCE(score,0) DESC, title
    """, (project_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def set_status(con: sqlite3.Connection, paper_id: int, new_status: str, score: Optional[int] = None):
    assert new_status in ("include","maybe")
    con.execute("UPDATE papers SET status = ?, score = COALESCE(?, score) WHERE id = ?", (new_status, score, paper_id))
