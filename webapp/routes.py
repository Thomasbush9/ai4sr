# webapp/routes.py
from flask import Blueprint, request, jsonify, render_template, make_response
from datetime import datetime
from webapp.db import get_db
from agents.orchestrator import literature_review, rag_answer
from db.repository import get_or_create_project, save_pico, get_pico, get_pico_expansion
from agents.pico import PICO, expand_pico
from agents.corpus_generator import generate_corpus
from utils.logger import get_logger
from functools import wraps

api_bp = Blueprint("api", __name__)
logger = get_logger("webapp.routes")


def handle_errors(f):
    """Decorator to standardize error handling across routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            logger.warning(f"Missing required field in {f.__name__}: {e}")
            return jsonify({"error": f"Missing required field: {e}"}), 400
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify({"error": "An internal error occurred"}), 500
    return decorated_function


def validate_int(value, field_name, min_val=None, max_val=None):
    """Validate and convert a value to integer."""
    try:
        int_val = int(value)
        if min_val is not None and int_val < min_val:
            raise ValueError(f"{field_name} must be at least {min_val}")
        if max_val is not None and int_val > max_val:
            raise ValueError(f"{field_name} must be at most {max_val}")
        return int_val
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid integer")


@api_bp.get("/health")
def health_check():
    """Health check endpoint for monitoring and Docker healthchecks."""
    try:
        # Check database connectivity
        with get_db() as db:
            db.execute("SELECT 1").fetchone()
        
        return jsonify({
            "status": "healthy",
            "service": "ai4sr",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503

@api_bp.post("/start")
@handle_errors
def start():
    """Start a new conversation."""
    data = request.get_json(force=True) if request.is_json else {}
    project_name = data.get("project_name", "default")
    
    if not isinstance(project_name, str):
        project_name = str(project_name)
    project_name = project_name.strip() or "default"
    
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
    
    logger.info(f"Started conversation {conv_id} for project {project_id}")
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

@api_bp.get("/settings")
def get_settings():
    """Get current runtime Azure settings (secrets masked)."""
    import settings_store
    settings = dict(settings_store.load())
    # Mask secrets for display
    for key in ("MICROSOFT_CLIENT_SECRET", "OPENAI_KEY"):
        if key in settings and settings[key]:
            v = settings[key]
            settings[key] = v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
    return jsonify(settings)


@api_bp.post("/settings")
@handle_errors
def save_settings():
    """Save runtime Azure settings and reset cached clients."""
    import settings_store
    from agents.azure_config import reset_clients

    data = request.get_json(force=True)
    ALLOWED_KEYS = {
        "AZURE_EXISTING_AIPROJECT_ENDPOINT",
        "MICROSOFT_TENANT_ID",
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
        "AZURE_AGENT_NAME",
        "AZURE_OPENAI_DIRECT_ENDPOINT",
        "OPENAI_KEY",
    }
    # Merge with existing settings so partial saves don't wipe unrelated fields
    existing = settings_store.load()
    for k, v in data.items():
        if k not in ALLOWED_KEYS:
            continue
        if v:  # set non-empty values
            existing[k] = v
        elif k in existing:  # clear explicitly emptied values
            del existing[k]
    settings_store.save(existing)
    reset_clients()
    return jsonify({"success": True})


@api_bp.post("/test-azure-config")
def test_azure_config():
    """Test if Azure OpenAI configuration is valid"""
    try:
        from agents.azure_config import chat_completion

        # Test with a simple request
        messages = [{"role": "user", "content": "Hello"}]
        response = chat_completion(messages, max_tokens=5)

        return jsonify({"success": True, "message": "Azure OpenAI configuration is valid"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@api_bp.post("/projects")
@handle_errors
def create_project():
    """Create a new project."""
    data = request.get_json(force=True) if request.is_json else {}
    project_name = data.get("name", "").strip()
    
    if not project_name:
        raise ValueError("Project name is required")
    
    if project_name.lower() == "default":
        raise ValueError("Project name 'default' is reserved")
    
    with get_db() as db:
        from db.repository import get_or_create_project
        
        project_id = get_or_create_project(db, project_name)
        db.commit()
        
        logger.info(f"Created project {project_id}: {project_name}")
        return jsonify({
            "message": f"Project '{project_name}' created successfully",
            "project_id": project_id,
            "name": project_name
        })

@api_bp.delete("/projects/<int:project_id>")
@handle_errors
def delete_project(project_id):
    """Delete a project and all its associated data"""
    from pathlib import Path
    import shutil
    
    with get_db() as db:
        # Check if project exists
        project = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        project_name = project['name']
        
        # Delete all associated data (ON DELETE CASCADE should handle most, but we'll be explicit)
        # Delete agent summaries
        db.execute("DELETE FROM agent_summaries WHERE project_id = ?", (project_id,))
        
        # Delete PICO data
        db.execute("DELETE FROM pico_expansions WHERE project_id = ?", (project_id,))
        db.execute("DELETE FROM pico WHERE project_id = ?", (project_id,))
        
        # Delete ingestion logs
        db.execute("DELETE FROM review_ingestion_logs WHERE project_id = ?", (project_id,))
        
        # Delete screening labels (papers will cascade)
        db.execute("DELETE FROM screening_labels WHERE project_id = ?", (project_id,))
        
        # Delete FTS data for papers
        db.execute("DELETE FROM papers_fts WHERE rowid IN (SELECT id FROM papers WHERE project_id = ?)", (project_id,))
        
        # Delete all papers for this project
        db.execute("DELETE FROM papers WHERE project_id = ?", (project_id,))
        
        # Delete all conversations and messages for this project
        db.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = ?)", (project_id,))
        db.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
        
        # Delete the project itself
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        
        db.commit()
        
        # Delete RAG embeddings directory for this project
        try:
            from config import REPO_ROOT
            rag_dir = REPO_ROOT / "data" / "rag_embeddings" / f"project_{project_id}"
            if rag_dir.exists():
                shutil.rmtree(rag_dir)
                logger.debug(f"Deleted RAG embeddings directory: {rag_dir}")
        except Exception as e:
            logger.warning(f"Failed to delete RAG embeddings directory: {e}")
            # Don't fail the deletion if RAG cleanup fails
        
        logger.info(f"Project {project_id} ({project_name}) deleted successfully")
        return jsonify({"message": f"Project '{project_name}' deleted successfully"})

@api_bp.post("/message")
@handle_errors
def message():
    """Handle a chat message."""
    data = request.get_json(force=True) if request.is_json else {}
    
    # Validate required fields
    if "conversation_id" not in data:
        raise ValueError("conversation_id is required")
    
    conv_id = validate_int(data["conversation_id"], "conversation_id", min_val=1)
    text = (data.get("text") or "").strip()
    modality = (data.get("modality") or "").strip()  # "literature" | "rag"
    project_name = data.get("project_id")  # Get the raw value first
    user_api_key = data.get("api_key")  # Get API key from frontend
    
    # Validate paper limit
    paper_limit = validate_int(data.get("paper_limit", 10), "paper_limit", min_val=1, max_val=50)
    
    logger.debug(f"Received message: conversation_id={conv_id}, modality={modality}, paper_limit={paper_limit}")
    
    # Ensure project_name is not None or empty, default to "default"
    if not project_name or (isinstance(project_name, str) and project_name.strip() == ""):
        project_name = "default"
    
    # Convert to int if it's a numeric string, otherwise treat as name
    if isinstance(project_name, str) and project_name.isdigit():
        project_id = int(project_name)
        logger.debug(f"Using numeric project_id: {project_id}")
    else:
        # Create or get project by name
        logger.debug(f"Creating/getting project with name: {repr(project_name)}")
        with get_db() as db:
            project_id = get_or_create_project(db, project_name)
            db.commit()
        logger.debug(f"Got project_id: {project_id}")

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
            logger.debug(f"Updated conversation {conv_id} to project {project_id}")
        elif not existing_conv:
            # Create conversation if it doesn't exist
            db.execute(
                "INSERT INTO conversations (id, project_id, created_at) VALUES (?, ?, ?)",
                (conv_id, project_id, datetime.utcnow().isoformat())
            )
            db.commit()
            logger.debug(f"Created conversation {conv_id} for project {project_id}")

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
            logger.info(f"Literature review completed for project {project_id}")
        except Exception as e:
            reply_core = f"Error during literature review: {e}"
            logger.error(f"Literature review failed: {e}", exc_info=True)

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
@handle_errors
def expand_project_pico(project_id):
    """Expand PICO into search queries using Azure AI Foundry."""
    logger.info(f"Starting PICO expansion for project {project_id}")
    
    # Get API key from request or use default
    data = request.get_json(force=True) if request.is_json else {}
    api_key = data.get("api_key")
    
    # Get PICO from database
    with get_db() as db:
        pico = get_pico(db, project_id)
        
        if not pico:
            logger.warning(f"PICO not found for project {project_id}")
            return jsonify({"error": "PICO not found for this project. Please create PICO first."}), 404
    
    logger.debug("PICO found, expanding...")
    # Expand PICO (this may take time - Azure API call)
    expansion_result = expand_pico(pico, project_id, api_key=api_key)
    
    logger.info(f"PICO expansion completed successfully for project {project_id}")
    return jsonify(expansion_result)


@api_bp.get("/projects/<int:project_id>/queries")
@handle_errors
def get_project_queries(project_id):
    """Get expanded queries for a project."""
    with get_db() as db:
        expansion = get_pico_expansion(db, project_id)
        
        if not expansion:
            return jsonify({"error": "No expansion found for this project. Please run expand-pico first."}), 404
        
        return jsonify(expansion)


@api_bp.post("/projects/<int:project_id>/generate-corpus")
@handle_errors
def generate_project_corpus(project_id):
    """Generate corpus for a project from stored queries.
    
    Uses server-side config limits. Ignores any max_results in request body.
    """
    logger.info(f"Starting corpus generation for project {project_id}")
    
    # Ignore max_results from request - use server config instead
    data = request.get_json(force=True) if request.is_json else {}
    # api_key can still be passed for compatibility, but max_results is ignored
    
    # Get expanded queries from database
    with get_db() as db:
        expansion = get_pico_expansion(db, project_id)
        
        if not expansion:
            logger.warning(f"No PICO expansion found for project {project_id}")
            return jsonify({
                "error": "No expansion found for this project. Please run expand-pico first."
            }), 404
        
        pubmed_query = expansion.get("pubmed_query")
        openalex_query = expansion.get("openalex_query")
        
        logger.debug(f"Found PICO expansion - PubMed query length: {len(pubmed_query) if pubmed_query else 0}, OpenAlex query length: {len(openalex_query) if openalex_query else 0}")
        
        if not pubmed_query and not openalex_query:
            logger.error(f"Both queries are empty for project {project_id}")
            return jsonify({
                "error": "PICO expansion produced empty queries. Please expand PICO again or check the PICO content."
            }), 400
    
    # Generate corpus (max_results parameter is ignored, uses config limits)
    logger.debug("Starting corpus generation from sources...")
    result = generate_corpus(
        project_id=project_id,
        pubmed_query=pubmed_query,
        openalex_query=openalex_query,
        max_results=None,  # Explicitly None - will use config limits
        api_key=data.get("api_key")
    )
    
    logger.info(f"Corpus generation completed successfully for project {project_id}")
    
    # Return simplified JSON response
    response_data = {
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
    }
    
    # Include abstract coverage if available
    if "abstract_coverage" in result:
        response_data["abstract_coverage"] = result["abstract_coverage"]
    
    return jsonify(response_data)


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
        
        # Update RAG embeddings: add include/maybe papers, remove excluded papers
        try:
            from agents.rag_agent import RAGAgent
            
            logger.info(f"Syncing RAG embeddings after screening for project {project_id}")
            rag_agent = RAGAgent(project_id=project_id)
            rag_agent.sync_papers_from_db(project_id)
            logger.info(f"RAG embeddings synced successfully for project {project_id}")
        except Exception as e:
            logger.warning(f"Failed to sync RAG embeddings after screening: {e}")
            # Don't fail the request if RAG sync fails
        
        return jsonify({
            "saved": result["saved"],
            "updated_papers": result["updated_papers"]
        })
        
    except Exception as e:
        logger.error(f"Error saving screening labels: {e}", exc_info=True)
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


@api_bp.get("/projects/<int:project_id>/export")
def export_included_papers_endpoint(project_id):
    """Export included papers in various formats."""
    try:
        from db.repository import get_included_papers, get_agent_summaries, get_project_overview
        from webapp.db import get_db
        import csv
        import io
        import json
        from datetime import datetime
        
        format_type = request.args.get('format', 'json').lower()
        
        if format_type not in ['csv', 'json', 'bibtex', 'ris', 'pdf']:
            return jsonify({"error": "Invalid format. Supported: csv, json, bibtex, ris, pdf"}), 400
        
        with get_db() as db:
            # Get project name
            project = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
            project_name = project['name'] if project else f"Project_{project_id}"
            
            # Get included papers
            papers = get_included_papers(db, project_id)
            
            # Get summaries
            summaries = get_agent_summaries(db, project_id)
            summary_map = {s["paper_id"]: s for s in summaries}
            
            # Get overview
            overview = get_project_overview(db, project_id)
            
            # Combine papers with summaries
            papers_data = []
            for paper in papers:
                paper_id = paper["paper_id"]
                summary = summary_map.get(paper_id)
                
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
                
                papers_data.append(paper_data)
        
        # Generate export based on format
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Title', 'Authors', 'Year', 'Venue', 'DOI', 'PMID', 'PMCID',
                'Abstract', 'Population', 'Intervention', 'Comparator', 'Outcomes',
                'Main Findings', 'Sample Size', 'Notes'
            ])
            
            # Write data
            for paper in papers_data:
                summary = paper.get('summary') or {}
                writer.writerow([
                    paper.get('title', ''),
                    paper.get('authors', ''),
                    paper.get('year', ''),
                    paper.get('venue', ''),
                    paper.get('doi', ''),
                    paper.get('pmid', ''),
                    paper.get('pmcid', ''),
                    paper.get('abstract', ''),
                    summary.get('population', ''),
                    summary.get('intervention', ''),
                    summary.get('comparator', ''),
                    summary.get('outcomes', ''),
                    summary.get('main_findings', ''),
                    summary.get('sample_size', ''),
                    summary.get('notes', '')
                ])
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{project_name}_included_papers_{datetime.now().strftime("%Y%m%d")}.csv"'
            return response
            
        elif format_type == 'json':
            export_data = {
                "project_name": project_name,
                "export_date": datetime.now().isoformat(),
                "papers_count": len(papers_data),
                "papers": papers_data,
                "overview": overview
            }
            response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{project_name}_included_papers_{datetime.now().strftime("%Y%m%d")}.json"'
            return response
            
        elif format_type == 'bibtex':
            output = io.StringIO()
            for idx, paper in enumerate(papers_data, 1):
                # Generate BibTeX key
                first_author = ""
                if paper.get('authors'):
                    authors = paper['authors'].split(';')[0].split(',')[0].strip()
                    first_author = authors.split()[0] if authors else ""
                year = str(paper.get('year', '')) if paper.get('year') else 'n.d.'
                key = f"{first_author}{year}{idx}".replace(' ', '').replace('.', '')[:20]
                
                output.write(f"@article{{{key},\n")
                output.write(f"  title = {{{paper.get('title', '')}}},\n")
                if paper.get('authors'):
                    output.write(f"  author = {{{paper.get('authors', '')}}},\n")
                if paper.get('year'):
                    output.write(f"  year = {{{paper.get('year')}}},\n")
                if paper.get('venue'):
                    output.write(f"  journal = {{{paper.get('venue', '')}}},\n")
                if paper.get('doi'):
                    output.write(f"  doi = {{{paper.get('doi', '')}}},\n")
                if paper.get('pmid'):
                    output.write(f"  pmid = {{{paper.get('pmid', '')}}},\n")
                if paper.get('abstract'):
                    # Escape braces in abstract
                    abstract = paper.get('abstract', '').replace('{', '{{').replace('}', '}}')
                    output.write(f"  abstract = {{{abstract}}},\n")
                output.write("}\n\n")
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{project_name}_included_papers_{datetime.now().strftime("%Y%m%d")}.bib"'
            return response
            
        elif format_type == 'ris':
            output = io.StringIO()
            for paper in papers_data:
                output.write("TY  - JOUR\n")
                if paper.get('title'):
                    output.write(f"TI  - {paper.get('title', '')}\n")
                if paper.get('authors'):
                    # RIS format uses one author per line
                    authors = paper.get('authors', '').split(';')
                    for author in authors:
                        author = author.strip()
                        if author:
                            output.write(f"AU  - {author}\n")
                if paper.get('year'):
                    output.write(f"PY  - {paper.get('year')}\n")
                if paper.get('venue'):
                    output.write(f"T2  - {paper.get('venue', '')}\n")
                if paper.get('doi'):
                    output.write(f"DO  - {paper.get('doi', '')}\n")
                if paper.get('pmid'):
                    output.write(f"PMID  - {paper.get('pmid', '')}\n")
                if paper.get('abstract'):
                    output.write(f"AB  - {paper.get('abstract', '')}\n")
                if paper.get('url'):
                    output.write(f"UR  - {paper.get('url', '')}\n")
                output.write("ER  - \n\n")
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="{project_name}_included_papers_{datetime.now().strftime("%Y%m%d")}.ris"'
            return response
            
        elif format_type == 'pdf':
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
                from reportlab.lib import colors
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    textColor=colors.HexColor('#1e293b'),
                    spaceAfter=12,
                )
                story.append(Paragraph(f"Included Papers: {project_name}", title_style))
                story.append(Spacer(1, 0.2*inch))
                
                # Overview if available
                if overview:
                    overview_style = ParagraphStyle(
                        'Overview',
                        parent=styles['BodyText'],
                        fontSize=11,
                        spaceAfter=12,
                    )
                    story.append(Paragraph("<b>Project Overview</b>", styles['Heading2']))
                    overview_text = overview.get('overview', '')
                    if overview_text:
                        story.append(Paragraph(overview_text.replace('\n', '<br/>'), overview_style))
                    story.append(Spacer(1, 0.2*inch))
                
                # Papers
                for idx, paper in enumerate(papers_data, 1):
                    if idx > 1:
                        story.append(PageBreak())
                    
                    # Paper title
                    story.append(Paragraph(f"<b>{idx}. {paper.get('title', 'No title')}</b>", styles['Heading2']))
                    story.append(Spacer(1, 0.1*inch))
                    
                    # Metadata table
                    metadata_data = []
                    if paper.get('authors'):
                        metadata_data.append(['Authors:', paper.get('authors', '')])
                    if paper.get('year'):
                        metadata_data.append(['Year:', str(paper.get('year'))])
                    if paper.get('venue'):
                        metadata_data.append(['Venue:', paper.get('venue', '')])
                    if paper.get('doi'):
                        metadata_data.append(['DOI:', paper.get('doi', '')])
                    if paper.get('pmid'):
                        metadata_data.append(['PMID:', paper.get('pmid', '')])
                    
                    if metadata_data:
                        metadata_table = Table(metadata_data, colWidths=[1.5*inch, 4.5*inch])
                        metadata_table.setStyle(TableStyle([
                            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        story.append(metadata_table)
                        story.append(Spacer(1, 0.15*inch))
                    
                    # Abstract
                    if paper.get('abstract'):
                        story.append(Paragraph("<b>Abstract</b>", styles['Heading3']))
                        abstract_text = paper.get('abstract', '').replace('\n', '<br/>')
                        story.append(Paragraph(abstract_text, styles['BodyText']))
                        story.append(Spacer(1, 0.15*inch))
                    
                    # Summary
                    summary = paper.get('summary')
                    if summary:
                        story.append(Paragraph("<b>Agent Summary</b>", styles['Heading3']))
                        summary_data = []
                        if summary.get('population'):
                            summary_data.append(['Population:', summary.get('population', '')])
                        if summary.get('intervention'):
                            summary_data.append(['Intervention:', summary.get('intervention', '')])
                        if summary.get('comparator'):
                            summary_data.append(['Comparator:', summary.get('comparator', '')])
                        if summary.get('outcomes'):
                            summary_data.append(['Outcomes:', summary.get('outcomes', '')])
                        if summary.get('main_findings'):
                            summary_data.append(['Main Findings:', summary.get('main_findings', '')])
                        if summary.get('sample_size'):
                            summary_data.append(['Sample Size:', summary.get('sample_size', '')])
                        if summary.get('notes'):
                            summary_data.append(['Notes:', summary.get('notes', '')])
                        
                        if summary_data:
                            summary_table = Table(summary_data, colWidths=[1.5*inch, 4.5*inch])
                            summary_table.setStyle(TableStyle([
                                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                                ('FONTSIZE', (0, 0), (-1, -1), 10),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                            ]))
                            story.append(summary_table)
                
                doc.build(story)
                buffer.seek(0)
                
                response = make_response(buffer.read())
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename="{project_name}_included_papers_{datetime.now().strftime("%Y%m%d")}.pdf"'
                return response
                
            except ImportError:
                return jsonify({"error": "PDF generation requires reportlab. Install with: pip install reportlab"}), 500
        
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

