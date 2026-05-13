from flask import Blueprint, request, g
from firebase_admin import firestore
from datetime import datetime, timezone, timedelta

from config import Collections
from models import Poll, PollOption
from utils import success, error
from middleware import login_required, admin_required

polls_bp = Blueprint("polls", __name__, url_prefix="/api/polls")


def _db():
    return firestore.client()


def _auto_close_expired(db, poll_data: dict, poll_ref) -> dict:
    """Auto-close a poll if its expires_at has passed."""
    expires_at = poll_data.get("expires_at")
    if expires_at and poll_data.get("status") == Poll.STATUS_ACTIVE:
        expiry_dt = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) > expiry_dt:
            poll_ref.update({
                "status":    Poll.STATUS_CLOSED,
                "closed_at": datetime.now(timezone.utc).isoformat(),
            })
            poll_data["status"]    = Poll.STATUS_CLOSED
            poll_data["closed_at"] = datetime.now(timezone.utc).isoformat()
    return poll_data


# ── POST /api/polls ───────────────────────────────────────────────────────────
@polls_bp.post("/")
@admin_required
def create_poll():
    """
    Create a new poll. Admin only.
    Body: {
        question, description?, options: [str,...],
        status?,
        expires_in_hours?   ← new: auto-close after N hours
    }
    """
    data     = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    options  = data.get("options", [])

    if not question:
        return error("Poll question is required.")
    if not isinstance(options, list) or len(options) < 2:
        return error("At least 2 options are required.")

    poll_options = [PollOption(text=str(o).strip()) for o in options if str(o).strip()]
    if len(poll_options) < 2:
        return error("At least 2 non-empty options are required.")

    # Optional expiry
    expires_at = None
    expires_in = data.get("expires_in_hours")
    if expires_in:
        try:
            hours      = float(expires_in)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        except ValueError:
            return error("expires_in_hours must be a number.")

    poll = Poll(
        question    = question,
        description = (data.get("description") or "").strip(),
        created_by  = g.user_id,
        options     = poll_options,
        status      = data.get("status", Poll.STATUS_ACTIVE),
        expires_at  = expires_at,
    )

    db = _db()
    poll_dict = poll.to_dict()
    db.collection(Collections.POLLS).document(poll.id).set(poll_dict)

    return success(data={"poll": poll_dict}, message="Poll created.", status=201)


# ── GET /api/polls ────────────────────────────────────────────────────────────
@polls_bp.get("/")
@login_required
def list_polls():
    """Return all polls, auto-closing any expired ones."""
    status_filter = request.args.get("status")
    db  = _db()
    ref = db.collection(Collections.POLLS)

    if status_filter in (Poll.STATUS_ACTIVE, Poll.STATUS_CLOSED):
        docs = ref.where(
            filter=firestore.FieldFilter("status", "==", status_filter)
        ).order_by("created_at", direction=firestore.Query.DESCENDING).get()
    else:
        docs = ref.order_by(
            "created_at", direction=firestore.Query.DESCENDING
        ).get()

    polls = []
    for d in docs:
        poll_data = _auto_close_expired(db, d.to_dict(), d.reference)
        polls.append(poll_data)

    return success(data={"polls": polls, "count": len(polls)})


# ── GET /api/polls/<poll_id> ──────────────────────────────────────────────────
@polls_bp.get("/<poll_id>")
@login_required
def get_poll(poll_id: str):
    """Return a single poll, auto-closing if expired."""
    db  = _db()
    ref = db.collection(Collections.POLLS).document(poll_id)
    doc = ref.get()
    if not doc.exists:
        return error("Poll not found.", 404)
    poll_data = _auto_close_expired(db, doc.to_dict(), ref)
    return success(data={"poll": poll_data})


# ── PATCH /api/polls/<poll_id>/close ─────────────────────────────────────────
@polls_bp.patch("/<poll_id>/close")
@admin_required
def close_poll(poll_id: str):
    """Manually close a poll. Admin only."""
    db  = _db()
    ref = db.collection(Collections.POLLS).document(poll_id)
    doc = ref.get()
    if not doc.exists:
        return error("Poll not found.", 404)
    if doc.to_dict()["status"] == Poll.STATUS_CLOSED:
        return error("Poll is already closed.")
    ref.update({
        "status":    Poll.STATUS_CLOSED,
        "closed_at": datetime.now(timezone.utc).isoformat(),
    })
    return success(message="Poll closed successfully.")


# ── DELETE /api/polls/<poll_id> ───────────────────────────────────────────────
@polls_bp.delete("/<poll_id>")
@admin_required
def delete_poll(poll_id: str):
    """Delete a poll and all its votes. Admin only."""
    db  = _db()
    ref = db.collection(Collections.POLLS).document(poll_id)
    if not ref.get().exists:
        return error("Poll not found.", 404)

    vote_docs = db.collection(Collections.VOTES).where(
        filter=firestore.FieldFilter("poll_id", "==", poll_id)
    ).get()
    for vdoc in vote_docs:
        vdoc.reference.delete()

    ref.delete()
    return success(message="Poll deleted.")


# ── GET /api/polls/<poll_id>/results ─────────────────────────────────────────
@polls_bp.get("/<poll_id>/results")
@login_required
def poll_results(poll_id: str):
    """Return detailed results with percentages."""
    db  = _db()
    ref = db.collection(Collections.POLLS).document(poll_id)
    doc = ref.get()
    if not doc.exists:
        return error("Poll not found.", 404)

    poll_data = _auto_close_expired(db, doc.to_dict(), ref)
    total     = poll_data.get("total_votes", 0)

    results = []
    for opt in poll_data.get("options", []):
        vc  = opt.get("vote_count", 0)
        pct = round((vc / total * 100), 2) if total > 0 else 0.0
        results.append({
            "id":         opt["id"],
            "text":       opt["text"],
            "vote_count": vc,
            "percentage": pct,
        })

    # Sort by votes descending
    results.sort(key=lambda x: x["vote_count"], reverse=True)

    return success(data={
        "poll_id":     poll_id,
        "question":    poll_data["question"],
        "status":      poll_data["status"],
        "total_votes": total,
        "expires_at":  poll_data.get("expires_at"),
        "results":     results,
    })
