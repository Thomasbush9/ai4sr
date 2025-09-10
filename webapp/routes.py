# webapp/routes.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from .db import get_db
from ai4sr.agents.orchestrator import literature_review, rag_answer

api_bp = Blueprint("api", __name__)

@api_bp.post("/start")
def start():
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO conversations (created_at) VALUES (?)",
            (datetime.utcnow().isoformat(),)
        )
        conv_id = cur.lastrowid
        db.commit()
    return jsonify({"conversation_id": conv_id})

@api_bp.post("/message")
def message():
    data = request.get_json(force=True)
    conv_id   = int(data["conversation_id"])
    text      = (data.get("text") or "").strip()
    modality  = (data.get("modality") or "").strip()  # "literature" | "rag"
    project_id = data.get("project_id")
    if isinstance(project_id, str) and project_id.isdigit():
        project_id = int(project_id)

    if not text:
        return jsonify({"reply": "Please enter a query."})
    if modality not in {"literature", "rag"}:
        return jsonify({"reply": f"Unknown modality: {modality}."})

    # 1) Save user message
    with get_db() as db:
        db.execute(
            "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, 'user', ?, ?)",
            (conv_id, text, datetime.utcnow().isoformat()),
        )
        db.commit()

    if modality == "literature":
        try:
            # Heavy work OUTSIDE DB context (to avoid locks)
            pid, included, maybes, selected_df, maybe_df = literature_review(
                query=text,
                project_id=project_id,
                n=10
            )
            project_id = pid  # ensure we carry the resolved id
            reply_core = "Literature review completed."
        except Exception as e:
            reply_core = f"Error during literature review: {e}"

        # Summarize & save assistant message
        with get_db() as db:
            (after_count,) = db.execute(
                "SELECT COUNT(*) FROM papers WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            newest = db.execute(
                """
                SELECT title, year FROM papers
                WHERE project_id = ?
                ORDER BY added_at DESC
                LIMIT 3
                """,
                (project_id,)
            ).fetchall()

            lines = [f"{reply_core} Project #{project_id} now has {after_count} papers."]
            if newest:
                lines.append("Newest entries:")
                for r in newest:
                    title = r["title"] or "Untitled"
                    yr = f" ({r['year']})" if r["year"] else ""
                    lines.append(f"• {title}{yr}")
            reply = "\n".join(lines)

            db.execute(
                "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
                (conv_id, reply, datetime.utcnow().isoformat()),
            )
            db.commit()

    else:  # RAG
        with get_db() as db:
            reply = rag_answer(text, project_id, db)  # make sure rag_answer filters by project_id
            db.execute(
                "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
                (conv_id, reply, datetime.utcnow().isoformat()),
            )
            db.commit()

    return jsonify({"reply": reply})

