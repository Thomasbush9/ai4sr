# webapp/routes.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from .db import get_db
from ai4sr.agents.orchestrator import literature_review, rag_answer
from ai4sr.db.repository import get_or_create_project

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
    project_name = data.get("project_id")  # Get the raw value first
    paper_limit = int(data.get("paper_limit", 10))  # Default to 10 if not provided
    # Validate paper limit
    paper_limit = max(1, min(50, paper_limit))  # Clamp between 1 and 50
    
    # Debug: print what we received
    print(f"DEBUG: Received project_id: {repr(project_name)}")
    print(f"DEBUG: Received paper_limit: {paper_limit}")
    
    # Ensure project_name is not None or empty, default to "default"
    if not project_name or (isinstance(project_name, str) and project_name.strip() == ""):
        project_name = "default"
    
    print(f"DEBUG: Final project_name: {repr(project_name)}")
    
    # Convert to int if it's a numeric string, otherwise treat as name
    if isinstance(project_name, str) and project_name.isdigit():
        project_id = int(project_name)
        print(f"DEBUG: Using numeric project_id: {project_id}")
    else:
        # Create or get project by name
        print(f"DEBUG: Creating/getting project with name: {repr(project_name)}")
        with get_db() as db:
            project_id = get_or_create_project(db, project_name)
            db.commit()
        print(f"DEBUG: Got project_id: {project_id}")

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
        literature_success = False
        try:
            # Heavy work OUTSIDE DB context (to avoid locks)
            pid, included, maybes, selected_df, maybe_df = literature_review(
                query=text,
                project_id=project_id,
                n=paper_limit
            )
            project_id = pid  # ensure we carry the resolved id
            reply_core = "Literature review completed."
            literature_success = True
        except Exception as e:
            reply_core = f"Error during literature review: {e}"
            print(f"DEBUG: Literature review failed: {e}")

        # Summarize & save assistant message
        with get_db() as db:
            if literature_success:
                # Only show papers if literature review was successful
                (after_count,) = db.execute(
                    "SELECT COUNT(*) FROM papers WHERE project_id = ?",
                    (project_id,)
                ).fetchone()
                newest = db.execute(
                    """
                    SELECT id, title, abstract, authors, year, venue, doi, doi_url, pubmed_url, url, pdf_path, status, score
                    FROM papers
                    WHERE project_id = ?
                    ORDER BY added_at DESC
                    LIMIT 10
                    """,
                    (project_id,)
                ).fetchall()

                # Create structured response
                response_data = {
                    "message": f"{reply_core} Project #{project_id} now has {after_count} papers.",
                    "papers": []
                }
                
                if newest:
                    for r in newest:
                        paper = {
                            "id": r["id"],
                            "title": r["title"] or "Untitled",
                            "abstract": r["abstract"] or "",
                            "authors": r["authors"] or "",
                            "year": r["year"],
                            "venue": r["venue"] or "",
                            "doi": r["doi"] or "",
                            "doi_url": r["doi_url"] or "",
                            "pubmed_url": r["pubmed_url"] or "",
                            "url": r["url"] or "",
                            "pdf_path": r["pdf_path"] or "",
                            "status": r["status"],
                            "score": r["score"]
                        }
                        response_data["papers"].append(paper)
                
                # For backward compatibility, also create a text reply
                lines = [response_data["message"]]
                if newest:
                    lines.append("Newest entries:")
                    for r in newest:
                        title = r["title"] or "Untitled"
                        yr = f" ({r['year']})" if r["year"] else ""
                        lines.append(f"• {title}{yr}")
                reply = "\n".join(lines)
            else:
                # If literature review failed, just show error message
                response_data = {
                    "message": reply_core,
                    "papers": []
                }
                reply = reply_core

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
            response_data = {"message": reply, "papers": []}

    # Return structured response for literature mode, simple reply for RAG mode
    if modality == "literature":
        return jsonify(response_data)
    else:
        return jsonify({"reply": reply})

