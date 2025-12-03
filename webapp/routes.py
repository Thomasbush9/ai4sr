# webapp/routes.py
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from webapp.db import get_db
from agents.orchestrator import literature_review, rag_answer
from db.repository import get_or_create_project, save_pico, get_pico, get_pico_expansion
from agents.pico import PICO, expand_pico
from agents.corpus_generator import generate_corpus

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
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (conversation_id,)).fetchall()
        
        return jsonify([{
            "role": m["role"],
            "text": m["content"],
            "created_at": m["created_at"]
        } for m in messages])

@api_bp.post("/test-openai")
def test_openai_key():
    """Test if an OpenAI API key is valid"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({"success": False, "error": "No API key provided"}), 400
        
        # Test the API key with a simple request
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Make a simple test request
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        
        return jsonify({"success": True, "message": "API key is valid"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@api_bp.delete("/projects/<int:project_id>")
def delete_project(project_id):
    """Delete a project and all its associated data"""
    try:
        with get_db() as db:
            # Check if project exists
            project = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return jsonify({"error": "Project not found"}), 404
            
            # Delete all conversations and messages for this project
            db.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = ?)", (project_id,))
            db.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
            
            # Delete all papers for this project
            db.execute("DELETE FROM papers WHERE project_id = ?", (project_id,))
            
            # Delete the project itself
            db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            
            db.commit()
            
            return jsonify({"message": f"Project '{project['name']}' deleted successfully"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.post("/message")
def message():
    data = request.get_json(force=True)
    conv_id   = int(data["conversation_id"])
    text      = (data.get("text") or "").strip()
    modality  = (data.get("modality") or "").strip()  # "literature" | "rag"
    project_name = data.get("project_id")  # Get the raw value first
    paper_limit = int(data.get("paper_limit", 10))  # Default to 10 if not provided
    user_api_key = data.get("api_key")  # Get API key from frontend
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
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
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
                n=paper_limit,
                api_key=user_api_key
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
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                (conv_id, reply, datetime.utcnow().isoformat()),
            )
            db.commit()

    else:  # RAG
        with get_db() as db:
            reply = rag_answer(text, project_id, db, api_key=user_api_key)  # Pass user's API key
            db.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                (conv_id, reply, datetime.utcnow().isoformat()),
            )
            db.commit()
            response_data = {"message": reply, "papers": []}

    # Return structured response for literature mode, simple reply for RAG mode
    if modality == "literature":
        return jsonify(response_data)
    else:
        return jsonify({"reply": reply})


@api_bp.post("/projects/<int:project_id>/pico")
def create_or_update_pico(project_id):
    """Create or update PICO for a project."""
    try:
        data = request.get_json(force=True) if request.is_json else {}
        
        # Validate required fields
        if "population" not in data:
            return jsonify({"error": "population is required"}), 400
        
        # Create PICO object
        pico = PICO(
            population=data.get("population", ""),
            intervention=data.get("intervention"),
            comparison=data.get("comparison"),
            outcome=data.get("outcome"),
            study_design=data.get("study_design"),
            extra_terms=data.get("extra_terms"),
        )
        
        # Save to database
        with get_db() as db:
            save_pico(db, project_id, pico)
            db.commit()
        
        return jsonify(pico.to_dict())
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/pico")
def get_project_pico(project_id):
    """Get PICO for a project."""
    try:
        with get_db() as db:
            pico = get_pico(db, project_id)
            
            if not pico:
                return jsonify({"error": "PICO not found for this project"}), 404
            
            return jsonify(pico.to_dict())
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/expand-pico")
def expand_project_pico(project_id):
    """Expand PICO into search queries using DSPy."""
    try:
        # Get API key from request or use default
        data = request.get_json(force=True) if request.is_json else {}
        api_key = data.get("api_key")
        
        # Get PICO from database
        with get_db() as db:
            pico = get_pico(db, project_id)
            
            if not pico:
                return jsonify({"error": "PICO not found for this project. Please create PICO first."}), 404
        
        # Expand PICO
        expansion_result = expand_pico(pico, project_id, api_key=api_key)
        
        return jsonify(expansion_result)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/queries")
def get_project_queries(project_id):
    """Get expanded queries for a project."""
    try:
        with get_db() as db:
            expansion = get_pico_expansion(db, project_id)
            
            if not expansion:
                return jsonify({"error": "No expansion found for this project. Please run expand-pico first."}), 404
            
            return jsonify(expansion)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/generate-corpus")
def generate_project_corpus(project_id):
    """Generate corpus for a project from stored queries.
    
    Uses server-side config limits. Ignores any max_results in request body.
    """
    try:
        # Ignore max_results from request - use server config instead
        data = request.get_json(force=True) if request.is_json else {}
        # api_key can still be passed for compatibility, but max_results is ignored
        
        # Get expanded queries from database
        with get_db() as db:
            expansion = get_pico_expansion(db, project_id)
            
            if not expansion:
                return jsonify({
                    "error": "No expansion found for this project. Please run expand-pico first."
                }), 404
            
            pubmed_query = expansion.get("pubmed_query")
            openalex_query = expansion.get("openalex_query")
        
        # Generate corpus (max_results parameter is ignored, uses config limits)
        result = generate_corpus(
            project_id=project_id,
            pubmed_query=pubmed_query,
            openalex_query=openalex_query,
            max_results=None,  # Explicitly None - will use config limits
            api_key=data.get("api_key")
        )
        
        # Return simplified JSON response
        return jsonify({
            "status": "completed",
            "project_id": project_id,
            "sources": {
                "pubmed": {
                    "fetched": result["pubmed_count"],
                    "unique": result["pubmed_unique"]
                },
                "openalex": {
                    "fetched": result["openalex_count"],
                    "unique": result["openalex_unique"]
                }
            },
            "total_unique": result["total_unique"],
            "inserted_count": result["inserted_count"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "status": "failed"}), 500


@api_bp.get("/projects/<int:project_id>/screening/next")
def get_next_screening_batch(project_id):
    """Get next batch of papers to label using active learning."""
    try:
        from agents.screener import get_next_batch
        
        batch_size = request.args.get('batch_size', 10, type=int)
        strategy = request.args.get('strategy', 'relevance', type=str)
        classifier_type = request.args.get('classifier', 'random_forest', type=str)
        
        # Validate strategy
        if strategy not in ('relevance', 'uncertainty'):
            return jsonify({"error": "strategy must be 'relevance' or 'uncertainty'"}), 400
        
        # Validate classifier_type
        if classifier_type not in ('logistic', 'svm', 'random_forest', 'naive_bayes'):
            return jsonify({"error": "classifier must be 'logistic', 'svm', 'random_forest', or 'naive_bayes'"}), 400
        
        # Validate batch_size
        batch_size = max(1, min(100, batch_size))  # Clamp between 1 and 100
        
        # Get next batch
        papers = get_next_batch(project_id, batch_size=batch_size, strategy=strategy, classifier_type=classifier_type)
        
        # Check if stopping rules triggered (empty papers list)
        from agents.screener import should_stop_screening
        if not papers and should_stop_screening(project_id):
            return jsonify({
                "project_id": project_id,
                "done": True,
                "papers": []
            })
        
        return jsonify({"papers": papers, "done": False})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/screening/label")
def save_screening_labels_endpoint(project_id):
    """Save screening labels for papers."""
    try:
        from db.repository import save_screening_labels
        from agents.screener import clear_model_cache
        from webapp.db import get_db
        
        data = request.get_json(force=True) if request.is_json else {}
        
        if "labels" not in data:
            return jsonify({"error": "labels field is required"}), 400
        
        labels_list = data["labels"]
        if not isinstance(labels_list, list):
            return jsonify({"error": "labels must be a list"}), 400
        
        # Convert list of dicts to dict mapping paper_id -> label
        labels_dict = {}
        for item in labels_list:
            if not isinstance(item, dict):
                continue
            paper_id = item.get("paper_id")
            label = item.get("label")
            
            if paper_id is None or label is None:
                continue
            
            # Validate label
            if label not in ("INCLUDE", "EXCLUDE"):
                continue
            
            labels_dict[int(paper_id)] = label
        
        if not labels_dict:
            return jsonify({"error": "No valid labels provided"}), 400
        
        # Save labels
        with get_db() as db:
            result = save_screening_labels(db, project_id, labels_dict)
            db.commit()
        
        # Clear model cache for this project to force retraining
        clear_model_cache(project_id)
        
        return jsonify({
            "saved": result["saved"],
            "updated_papers": result["updated_papers"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/screening/stats")
def get_screening_stats_endpoint(project_id):
    """Get screening statistics for a project."""
    try:
        from db.repository import get_screening_stats
        from agents.screener import classifier_ready
        from webapp.db import get_db
        
        with get_db() as db:
            stats = get_screening_stats(db, project_id)
        
        # Add classifier readiness
        stats["classifier_ready"] = classifier_ready(project_id)
        
        # Check if cold-start was used (any labels with source='cold_agent')
        # Handle case where source column might not exist yet
        try:
            cold_start_check = db.execute("""
                SELECT COUNT(*) as count
                FROM screening_labels
                WHERE project_id = ? AND source = 'cold_agent'
            """, (project_id,)).fetchone()
            stats["cold_start_used"] = (cold_start_check["count"] > 0) if cold_start_check else False
        except Exception:
            # Source column doesn't exist yet, default to False
            stats["cold_start_used"] = False
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/screening/status")
def get_screening_status_endpoint(project_id):
    """Get screening status for a project (alias for /stats with same response)."""
    return get_screening_stats_endpoint(project_id)


@api_bp.post("/projects/<int:project_id>/screening/auto-label")
def auto_label_papers_endpoint(project_id):
    """Auto-label remaining unscreened papers using trained classifier."""
    try:
        from agents.screener import auto_label_papers
        
        classifier_type = request.args.get('classifier', 'random_forest', type=str)
        
        # Validate classifier_type
        if classifier_type not in ('logistic', 'svm', 'random_forest', 'naive_bayes'):
            return jsonify({"error": "classifier must be 'logistic', 'svm', 'random_forest', or 'naive_bayes'"}), 400
        
        # Optional thresholds in query params
        include_threshold = request.args.get('include_threshold', 0.8, type=float)
        exclude_threshold = request.args.get('exclude_threshold', 0.2, type=float)
        
        # Validate thresholds
        if not 0.0 <= exclude_threshold < include_threshold <= 1.0:
            return jsonify({"error": "Thresholds must satisfy 0 <= exclude_threshold < include_threshold <= 1"}), 400
        
        # Run auto-labeling
        result = auto_label_papers(
            project_id,
            classifier_type=classifier_type,
            include_threshold=include_threshold,
            exclude_threshold=exclude_threshold
        )
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/screening/cold-start")
def cold_start_endpoint(project_id):
    """Run cold-start agent to label initial papers."""
    try:
        from agents.cold_start_agent import run_cold_start
        from db.repository import get_unlabeled_papers
        from webapp.db import get_db
        
        # Get API key and n from request if provided
        data = request.get_json(force=True) if request.is_json else {}
        api_key = data.get("api_key")
        n = data.get("n", 10)
        
        # Validate n
        n = max(1, min(50, int(n)))  # Clamp between 1 and 50
        
        # Check if project exists and has PICO
        with get_db() as db:
            # Check if project exists
            project = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not project:
                return jsonify({"error": "Project not found"}), 404
            
            # Check if there are enough UNSCREENED papers
            unlabeled = get_unlabeled_papers(db, project_id, limit=n)
            if len(unlabeled) < n:
                return jsonify({
                    "error": f"Not enough unscreened papers. Found {len(unlabeled)}, requested {n}."
                }), 400
        
        # Run cold-start
        result = run_cold_start(project_id, n=n, api_key=api_key)
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/agent-review")
def agent_review_endpoint(project_id):
    """Review included papers and generate structured summaries."""
    try:
        from agents.review_agent import review_included_papers
        from webapp.db import get_db
        
        data = request.get_json(force=True) if request.is_json else {}
        pico = data.get("pico")  # Optional PICO context
        user_api_key = data.get("api_key")  # Optional API key
        
        # Run agent review
        result = review_included_papers(
            project_id=project_id,
            pico=pico,
            api_key=user_api_key
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/included-papers")
def get_included_papers_endpoint(project_id):
    """Get all included papers with their summaries."""
    try:
        from db.repository import get_included_papers, get_agent_summaries
        from webapp.db import get_db
        
        with get_db() as db:
            # Get included papers
            papers = get_included_papers(db, project_id)
            
            # Get summaries
            summaries = get_agent_summaries(db, project_id)
            
            # Create a map of paper_id -> summary
            summary_map = {s["paper_id"]: s for s in summaries}
            
            # Combine papers with summaries
            result = []
            for paper in papers:
                paper_id = paper["paper_id"]
                summary = summary_map.get(paper_id)
                
                # Ensure all metadata fields are included
                paper_data = {
                    "id": paper_id,
                    "title": paper.get("title", "") or "",
                    "abstract": paper.get("abstract", "") or "",
                    "authors": paper.get("authors", "") or "",
                    "year": paper.get("year"),
                    "venue": paper.get("venue", "") or "",
                    "doi": paper.get("doi", "") or "",
                    "pmid": paper.get("pmid", "") or "",
                    "pmcid": paper.get("pmcid", "") or "",
                    "url": paper.get("url", "") or "",
                    "pubmed_url": paper.get("pubmed_url", "") or "",
                    "doi_url": paper.get("doi_url", "") or "",
                    "summary": None
                }
                
                if summary:
                    paper_data["summary"] = {
                        "population": summary.get("population", "") or "",
                        "intervention": summary.get("intervention", "") or "",
                        "comparator": summary.get("comparator", "") or "",
                        "outcomes": summary.get("outcomes", "") or "",
                        "main_findings": summary.get("main_findings", "") or "",
                        "sample_size": summary.get("sample_size", "") or "",
                        "notes": summary.get("notes", "") or ""
                    }
                
                result.append(paper_data)
            
            return jsonify({"papers": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/projects/<int:project_id>/overview")
def get_project_overview_endpoint(project_id):
    """Get project overview/synthesis."""
    try:
        from db.repository import get_project_overview
        from webapp.db import get_db
        
        with get_db() as db:
            overview = get_project_overview(db, project_id)
            
            if not overview:
                return jsonify({"error": "No overview found for this project. Run agent review first."}), 404
            
            return jsonify(overview)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/projects/<int:project_id>/chat")
def chat_endpoint(project_id):
    """Chat endpoint for querying agent summaries and papers using RAG."""
    try:
        from agents.orchestrator import rag_answer
        
        data = request.get_json(force=True) if request.is_json else {}
        question = data.get("question", "").strip()
        user_api_key = data.get("api_key")  # Optional API key
        
        if not question:
            return jsonify({"error": "question field is required"}), 400
        
        # Use existing rag_answer function which now works with summaries
        answer = rag_answer(question, project_id, api_key=user_api_key)
        
        return jsonify({"answer": answer})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/db-viewer")
def db_viewer():
    """Display papers for a specific project."""
    try:
        project_id = request.args.get('project_id', type=int)
        page = request.args.get('page', 1, type=int)
        limit = 100
        offset = (page - 1) * limit
        
        with get_db() as db:
            # Get project name if project_id is provided
            project_name = None
            if project_id:
                project_row = db.execute(
                    "SELECT name FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project_row:
                    project_name = project_row['name']
            
            # Build query for papers
            if project_id:
                count_query = "SELECT COUNT(*) as count FROM papers WHERE project_id = ?"
                papers_query = """
                    SELECT id, title, authors, abstract, year, venue, doi, status, 
                           added_at, pmid, pmcid
                    FROM papers 
                    WHERE project_id = ?
                    ORDER BY added_at DESC
                    LIMIT ? OFFSET ?
                """
                count_row = db.execute(count_query, (project_id,)).fetchone()
                papers_result = db.execute(papers_query, (project_id, limit, offset)).fetchall()
            else:
                # If no project_id, show all papers
                count_query = "SELECT COUNT(*) as count FROM papers"
                papers_query = """
                    SELECT id, title, authors, abstract, year, venue, doi, status, 
                           added_at, pmid, pmcid, project_id
                    FROM papers 
                    ORDER BY added_at DESC
                    LIMIT ? OFFSET ?
                """
                count_row = db.execute(count_query).fetchone()
                papers_result = db.execute(papers_query, (limit, offset)).fetchall()
            
            total_count = count_row['count'] if count_row else 0
            papers = [dict(row) for row in papers_result]
            
            # Get project names for all papers if showing all
            if not project_id and papers:
                project_ids = [p.get('project_id') for p in papers if p.get('project_id')]
                if project_ids:
                    projects_result = db.execute(
                        "SELECT id, name FROM projects WHERE id IN ({})".format(
                            ','.join(['?'] * len(project_ids))
                        ),
                        project_ids
                    ).fetchall()
                    project_map = {p['id']: p['name'] for p in projects_result}
                    for paper in papers:
                        if paper.get('project_id'):
                            paper['project_name'] = project_map.get(paper['project_id'], 'Unknown')
            
            has_more = total_count > (offset + limit)
            
            return render_template('db_viewer.html', 
                                 papers=papers,
                                 project_id=project_id,
                                 project_name=project_name,
                                 total_count=total_count,
                                 page=page,
                                 has_more=has_more,
                                 limit=limit)
            
    except Exception as e:
        import traceback
        return f"Error loading database: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

