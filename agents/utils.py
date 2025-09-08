from typing import Iterable, List, Dict, Optional, Union
from __future__ import annotations

from agents.paper_finder import STOPWORDS


# -- functions for paper findings script

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
