from __future__ import annotations
from typing import Iterable, List, Dict, Optional, Union


# -- functions for paper findings script
STOPWORDS = {"and","or","the","of","in","on","for","with","to"}
def _dedupe_keep_order(strings: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for s in strings:
        if not isinstance(s, str):
            continue
        t = s.strip()
        if not t or t.lower() in STOPWORDS:
            continue
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    return out

def _quote_if_needed(term: str) -> str:
    t = term.strip().strip('"')
    return f'"{t}"' if any(ch in t for ch in [" ", "-"]) else t

def _tag(term: str, field: str) -> str:
    # field can be tiab, tw, mh, au, etc. Default is tiab.
    esc = _quote_if_needed(term)
    return f"{esc}[{field}]" if esc else ""

def _render_synonym_block(terms: List[str], field: str) -> str:
    terms = _dedupe_keep_order(terms)
    pieces = [_tag(t, field) for t in terms if t]
    pieces = [p for p in pieces if p]
    return "(" + " OR ".join(pieces) + ")" if pieces else ""

def build_pubmed_query_from_keywords(
    keywords: Iterable[str],
    *,
    field: str = "tiab",
    mesh_hints: Optional[Dict[str, str]] = None,
) -> str:
    """
    Most general builder: a single OR block from a flat list of keywords.
    Optionally appends MeSH hints (e.g., {"cocaine": '"Cocaine"[mh]'}).
    """
    kws = _dedupe_keep_order(keywords)
    block = _render_synonym_block(kws, field)
    # add MeSH hints if provided and relevant terms appear
    if mesh_hints:
        mh_terms = []
        low = {k.lower() for k in kws}
        for key, mh in mesh_hints.items():
            if key.lower() in low and mh:
                mh_terms.append(mh)
        if mh_terms and block:
            # insert before the closing parenthesis
            block = block[:-1] + " OR " + " OR ".join(mh_terms) + ")"
    return block

def build_pubmed_query_from_concepts(
    concepts: List[Iterable[str]],
    *,
    field: str = "tiab",
    mesh_hints: Optional[Dict[str, str]] = None,
) -> str:
    """
    Preferred when you know concept groups (A, B, C...):
      concepts = [
        ["population synonym 1", "population synonym 2"],
        ["intervention synonym 1", "intervention synonym 2"],
        ...
      ]
    Produces: (A1 OR A2) AND (B1 OR B2) AND ...
    Optionally appends MeSH hints if keys appear in any group.
    """
    blocks: List[str] = []
    seen_any: set[str] = set()
    for syns in concepts:
        syns = _dedupe_keep_order(syns)
        if not syns:
            continue
        blocks.append(_render_synonym_block(syns, field))
        seen_any |= {s.lower() for s in syns}

    if mesh_hints and blocks:
        mh_terms = [mh for key, mh in mesh_hints.items() if key.lower() in seen_any and mh]
        if mh_terms:
            # Add MeSH hints as an additional AND block
            blocks.append("(" + " OR ".join(mh_terms) + ")")

    # remove empties and AND the rest
    blocks = [b for b in blocks if b]
    return " AND ".join(blocks)

def append_filters(
    query: str,
    *,
    english: bool = False,
    humans: bool = False,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> str:
    if not query:
        return query
    parts = [query]
    if english:
        parts.append("english[lang]")
    if humans:
        parts.append("Humans[mh]")
    if year_from or year_to:
        y1 = str(year_from or 1800)
        y2 = str(year_to or 3000)
        parts.append(f'("{y1}"[dp] : "{y2}"[dp])')
    return " AND ".join(parts)
