from flask import Blueprint, request, jsonify
from datetime import datetime
from .db import get_db
from .services.engines import run_literature_review, run_rag

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
    conv_id = int(data["conversation_id"])
    text = data["text"].strip()
    modality = data.get("modality")  # required now

    with get_db() as db:
        # Save user msg
        db.execute(
            "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, 'user', ?, ?)",
            (conv_id, text, datetime.utcnow().isoformat()),
        )

        if modality == "literature":
            reply = run_literature_review(text, conv_id, db)
        elif modality == "rag":
            reply = run_rag(text, conv_id, db)
        else:
            reply = f"Unknown modality: {modality}"

        # Save assistant msg
        db.execute(
            "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
            (conv_id, reply, datetime.utcnow().isoformat()),
        )
        db.commit()

    return jsonify({"reply": reply})

@api_bp.get("/history/<int:conv_id>")
def history(conv_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT role, text, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conv_id,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])

