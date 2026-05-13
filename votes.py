from flask import Blueprint, request, g
from firebase_admin import firestore

from config import Collections
from models import Vote, Poll
from utils import success, error
from middleware import login_required

votes_bp = Blueprint("votes", __name__, url_prefix="/api/votes")


def _db():
    return firestore.client()


# ── POST /api/votes ───────────────────────────────────────────────────────────
@votes_bp.post("/")
@login_required
def cast_vote():
    """
    Cast a vote.
    Body: { poll_id, option_id }

    Rules enforced:
      • Poll must exist and be active.
      • Voter must not have already voted in this poll (one-vote-per-user).
      • option_id must belong to the poll.
    Uses a Firestore transaction to atomically:
      1. Write the Vote document.
      2. Increment option.vote_count on the Poll document.
      3. Increment poll.total_votes.
    """
    data      = request.get_json(silent=True) or {}
    poll_id   = (data.get("poll_id")   or "").strip()
    option_id = (data.get("option_id") or "").strip()

    if not poll_id or not option_id:
        return error("poll_id and option_id are required.")

    db       = _db()
    poll_ref = db.collection(Collections.POLLS).document(poll_id)

    @firestore.transactional
    def _transact(transaction):
        poll_snap = poll_ref.get(transaction=transaction)
        if not poll_snap.exists:
            raise ValueError("Poll not found.")

        poll_data = poll_snap.to_dict()

        if poll_data["status"] != Poll.STATUS_ACTIVE:
            raise PermissionError("This poll is closed.")

        # Validate option belongs to poll
        opt_ids = [o["id"] for o in poll_data.get("options", [])]
        if option_id not in opt_ids:
            raise ValueError("Invalid option_id for this poll.")

        # Check duplicate vote (compound key: voter_id + poll_id)
        dup_key = f"{g.user_id}_{poll_id}"
        dup_ref = db.collection(Collections.VOTES).document(dup_key)
        dup_snap = dup_ref.get(transaction=transaction)
        if dup_snap.exists:
            raise PermissionError("You have already voted in this poll.")

        # Build vote doc
        vote = Vote(
            id        = dup_key,           # deterministic ID prevents race duplication
            poll_id   = poll_id,
            option_id = option_id,
            voter_id  = g.user_id,
        )
        transaction.set(dup_ref, vote.to_dict())

        # Increment option vote_count and total_votes on the poll doc
        updated_options = []
        for opt in poll_data["options"]:
            if opt["id"] == option_id:
                opt = {**opt, "vote_count": opt.get("vote_count", 0) + 1}
            updated_options.append(opt)

        transaction.update(poll_ref, {
            "options":     updated_options,
            "total_votes": firestore.Increment(1),
        })

        return vote

    try:
        transaction = db.transaction()
        vote        = _transact(transaction)
        return success(
            data    = {"vote": vote.to_dict()},
            message = "Vote cast successfully.",
            status  = 201,
        )
    except PermissionError as e:
        return error(str(e), 403)
    except ValueError as e:
        return error(str(e), 404)
    except Exception as e:
        return error(f"Failed to cast vote: {e}", 500)


# ── GET /api/votes/my-vote/<poll_id> ─────────────────────────────────────────
@votes_bp.get("/my-vote/<poll_id>")
@login_required
def my_vote(poll_id: str):
    """
    Check whether the current user has voted in a given poll.
    Returns the vote document if yes, or null.
    """
    db     = _db()
    dup_key = f"{g.user_id}_{poll_id}"
    doc    = db.collection(Collections.VOTES).document(dup_key).get()

    if doc.exists:
        return success(data={"voted": True,  "vote": doc.to_dict()})
    return success(data={"voted": False, "vote": None})


# ── GET /api/votes/history ────────────────────────────────────────────────────
@votes_bp.get("/history")
@login_required
def vote_history():
    """
    Return all polls the current user has voted in,
    with the option they chose.
    """
    db    = _db()
    docs  = db.collection(Collections.VOTES).where("voter_id", "==", g.user_id).get()
    votes = [d.to_dict() for d in docs]
    return success(data={"votes": votes, "count": len(votes)})
