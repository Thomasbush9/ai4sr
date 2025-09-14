# webapp/routes.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from webapp.db import get_db
from agents.orchestrator import literature_review, rag_answer
from db.repository import get_or_create_project

api_bp = Blueprint("api", __name__)

@api_bp.post("/start")
def start():
    data = request.get_json(force=True) if request.is_json else {}
    project_name = data.get("project_name", "default")
    
    with get_db() as db:
        # Get or create project
        project_id = get_or_create_project(db, project_name)
        
        # Create conversation linked to project
        cur = db.execute(
            "INSERT INTO conversations (project_id, created_at) VALUES (?, ?)",
            (project_id, datetime.utcnow().isoformat())
        )
        conv_id = cur.lastrowid
        db.commit()
    return jsonify({"conversation_id": conv_id, "project_id": project_id})

@api_bp.get("/projects")
def get_projects():
    """Get all projects with their conversation counts"""
    with get_db() as db:
        projects = db.execute("""
            SELECT 
                p.id, 
                p.name, 
                p.created_at,
                COUNT(DISTINCT c.id) as conversation_count,
                COUNT(DISTINCT papers.id) as paper_count,
                MAX(c.created_at) as last_conversation
            FROM projects p
            LEFT JOIN conversations c ON p.id = c.project_id
            LEFT JOIN papers ON p.id = papers.project_id
            GROUP BY p.id, p.name, p.created_at
            ORDER BY last_conversation DESC, p.created_at DESC
        """).fetchall()
        
        return jsonify([{
            "id": p["id"],
            "name": p["name"],
            "created_at": p["created_at"],
            "conversation_count": p["conversation_count"],
            "paper_count": p["paper_count"],
            "last_conversation": p["last_conversation"]
        } for p in projects])

@api_bp.get("/conversations/<int:project_id>")
def get_conversations(project_id):
    """Get conversations for a specific project"""
    with get_db() as db:
        conversations = db.execute("""
            SELECT c.id, c.created_at, 
                   COUNT(m.id) as message_count,
                   MIN(m.created_at) as first_message,
                   MAX(m.created_at) as last_message
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.project_id = ?
            GROUP BY c.id, c.created_at
            ORDER BY c.created_at DESC
            LIMIT 20
        """, (project_id,)).fetchall()
        
        return jsonify([{
            "id": c["id"],
            "created_at": c["created_at"],
            "message_count": c["message_count"],
            "first_message": c["first_message"],
            "last_message": c["last_message"]
        } for c in conversations])

@api_bp.get("/conversations/<int:conversation_id>/messages")
def get_conversation_messages(conversation_id):
    """Get messages for a specific conversation"""
    with get_db() as db:
        messages = db.execute("""
            SELECT role, text, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (conversation_id,)).fetchall()
        
        return jsonify([{
            "role": m["role"],
            "text": m["text"],
            "created_at": m["created_at"]
        } for m in messages])

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

    # Ensure conversation is linked to the project
    with get_db() as db:
        # Check if conversation exists and update project_id if needed
        existing_conv = db.execute(
            "SELECT project_id FROM conversations WHERE id = ?", 
            (conv_id,)
        ).fetchone()
        
        if existing_conv and existing_conv["project_id"] != project_id:
            # Update conversation to link to correct project
            db.execute(
                "UPDATE conversations SET project_id = ? WHERE id = ?",
                (project_id, conv_id)
            )
            db.commit()
            print(f"DEBUG: Updated conversation {conv_id} to project {project_id}")
        elif not existing_conv:
            # Create conversation if it doesn't exist
            db.execute(
                "INSERT INTO conversations (id, project_id, created_at) VALUES (?, ?, ?)",
                (conv_id, project_id, datetime.utcnow().isoformat())
            )
            db.commit()
            print(f"DEBUG: Created conversation {conv_id} for project {project_id}")

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
                    SELECT id, title, abstract, authors, year, venue, doi, doi_url, pubmed_url, url, pdf_path, status, score, rationale
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
                            "score": r["score"],
                            "rationale": r["rationale"] or ""
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

