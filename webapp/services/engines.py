from datetime import datetime
from agents.orchestrator import literature_review
# Import your real logic here:
# from agents.literature import run as lit_run
# from agents.rag import answer as rag_answer

def run_literature_review(query: str, project_id: int, db_conn) -> str:
    """
    Calls your literature_review() which already saves papers.
    Then shows a friendly summary back to the chat.
    """
    try:
        # Call your existing pipeline
        literature_review(query, project_id)

        # Count new papers
        (count,) = db_conn.execute(
            "SELECT COUNT(*) FROM papers WHERE project_id = ?",
            (project_id,)
        ).fetchone()

        # Show 3 newest
        newest = db_conn.execute(
            """
            SELECT title, year FROM papers
            WHERE project_id = ?
            ORDER BY added_at DESC
            LIMIT 3
            """,
            (project_id,)
        ).fetchall()

        lines = [f"Literature review complete. Project now has {count} papers."]
        if newest:
            lines.append("Newest entries:")
            for r in newest:
                yr = f" ({r['year']})" if r["year"] else ""
                lines.append(f"• {r['title']}{yr}")
        return "\n".join(lines)

    except Exception as e:
        return f"Error during literature review: {e}"


def run_rag(query: str, db_conn):
    # return rag_answer(query, db_conn=db_conn)
    return f"[RAG] (stub) {query}"

