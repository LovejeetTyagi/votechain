/* ─── dashboard.js — VoteChain frontend dashboard ────────────────────────
   Handles:
     • enterDashboard()      — set up header + load data
     • renderPolls()         — render poll cards with live results
     • castVote()            — POST to /api/votes
     • createPoll / modal    — admin poll creation form
     • setFilter()           — active / closed / all tab filtering
   ─────────────────────────────────────────────────────────────────────────── */

let _polls       = [];          // cached polls
let _myVotes     = {};          // { poll_id: vote }
let _currentUser = null;
let _filter      = "all";

/* ── Enter dashboard ────────────────────────────────────────────────────── */
function enterDashboard(user) {
  _currentUser = user;

  // Show header
  document.getElementById("headerRight").style.display = "flex";
  document.getElementById("avatarEl").textContent =
    user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
  document.getElementById("userNameEl").textContent = user.name;

  const roleEl = document.getElementById("roleEl");
  roleEl.textContent = user.role;
  roleEl.className   = "badge-role " + (user.role === "admin" ? "badge-admin" : "badge-voter");

  // Admin gets "Create Poll" button
  if (user.role === "admin") {
    document.getElementById("createPollBtn").style.display = "";
  }

  // Switch screens
  document.getElementById("screenAuth").classList.remove("active");
  document.getElementById("screenDash").classList.add("active");

  loadDashboard();
  showToast(`Welcome back, ${user.name.split(" ")[0]}! 👋`, "✅");
}

/* ── Load all data ──────────────────────────────────────────────────────── */
async function loadDashboard() {
  showLoading(true);

  // Fetch polls
  const pollsRes = await apiFetch("/api/polls");
  if (pollsRes.success) {
    _polls = pollsRes.data.polls;
  }

  // Fetch my vote history
  const histRes = await apiFetch("/api/votes/history");
  if (histRes.success) {
    _myVotes = {};
    histRes.data.votes.forEach(v => { _myVotes[v.poll_id] = v; });
  }

  showLoading(false);
  _updateStats();
  renderPolls();
}

/* ── Stats ──────────────────────────────────────────────────────────────── */
function _updateStats() {
  document.getElementById("statActive").textContent =
    _polls.filter(p => p.status === "active").length;
  document.getElementById("statVotes").textContent  =
    _polls.reduce((s, p) => s + (p.total_votes || 0), 0);
  document.getElementById("statMyVotes").textContent =
    Object.keys(_myVotes).length;
}

/* ── Filter tabs ────────────────────────────────────────────────────────── */
function setFilter(filter, el) {
  _filter = filter;
  document.querySelectorAll(".ftab").forEach(t => t.classList.remove("active"));
  if (el) el.classList.add("active");
  renderPolls();
}

/* ── Render polls ───────────────────────────────────────────────────────── */
function renderPolls() {
  const grid = document.getElementById("pollsGrid");
  let polls  = _polls;

  if (_filter === "active") polls = polls.filter(p => p.status === "active");
  if (_filter === "closed") polls = polls.filter(p => p.status === "closed");

  if (!polls.length) {
    grid.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🗳️</div>
      <p>No polls here yet.</p>
    </div>`;
    return;
  }

  grid.innerHTML = polls.map(poll => _pollCard(poll)).join("");
}

function _pollCard(poll) {
  const myVote  = _myVotes[poll.id];
  const myOptId = myVote ? myVote.option_id : null;
  const total   = poll.total_votes || 0;
  const isAdmin = _currentUser?.role === "admin";
  const canVote = poll.status === "active" && !myOptId && !isAdmin;
  const showPct = myOptId || poll.status === "closed" || isAdmin;

  const optsHtml = (poll.options || []).map(opt => {
    const pct   = total > 0 ? Math.round((opt.vote_count / total) * 100) : 0;
    const voted = myOptId === opt.id;
    return `
      <div class="option-bar ${voted ? "voted" : ""}"
           onclick="${canVote ? `castVote('${poll.id}','${opt.id}')` : ""}">
        ${showPct ? `<div class="option-fill" style="width:${pct}%"></div>` : ""}
        <div class="option-text">
          <span>${opt.text}${voted ? " ✓" : ""}</span>
          ${showPct ? `<span class="option-pct">${pct}% · ${opt.vote_count}</span>` : "<span></span>"}
        </div>
      </div>`;
  }).join("");

  const adminBtns = isAdmin ? `
    <div class="admin-actions">
      ${poll.status === "active"
        ? `<button class="btn btn-danger btn-sm" onclick="closePoll('${poll.id}')">Close</button>`
        : ""}
      <button class="btn btn-ghost btn-sm" onclick="deletePoll('${poll.id}')">Delete</button>
    </div>` : "";

  const voterHint = !isAdmin
    ? (canVote
        ? `<span class="hint-vote">Tap an option to vote</span>`
        : myOptId
          ? `<span class="hint-voted">✓ Vote recorded</span>`
          : `<span class="hint-closed">Voting closed</span>`)
    : "";

  return `
    <div class="poll-card" id="card-${poll.id}">
      <div class="poll-top">
        <div>
          <div class="poll-title">${poll.question}</div>
          ${poll.description ? `<div class="poll-meta">${poll.description}</div>` : ""}
        </div>
        <span class="status-pill ${poll.status === "active" ? "status-active" : "status-closed"}">
          ${poll.status === "active" ? "● Active" : "Closed"}
        </span>
      </div>
      <div class="poll-options">${optsHtml}</div>
      <div class="poll-footer">
        <span class="vote-count">🗳 ${total} vote${total !== 1 ? "s" : ""}</span>
        ${adminBtns || voterHint}
      </div>
    </div>`;
}

/* ── Cast vote ──────────────────────────────────────────────────────────── */
async function castVote(pollId, optionId) {
  showLoading(true);
  const res = await apiFetch("/api/votes", "POST", { poll_id: pollId, option_id: optionId });
  showLoading(false);

  if (!res.success) return showToast(res.message, "❌");

  // Update local cache
  _myVotes[pollId] = res.data.vote;
  const poll = _polls.find(p => p.id === pollId);
  if (poll) {
    poll.options = poll.options.map(o =>
      o.id === optionId ? { ...o, vote_count: o.vote_count + 1 } : o
    );
    poll.total_votes = (poll.total_votes || 0) + 1;
  }
  _updateStats();
  renderPolls();
  showToast("Vote cast! Results updated live.", "🗳️");
}

/* ── Admin: close poll ──────────────────────────────────────────────────── */
async function closePoll(pollId) {
  showLoading(true);
  const res = await apiFetch(`/api/polls/${pollId}/close`, "PATCH");
  showLoading(false);
  if (!res.success) return showToast(res.message, "❌");

  const poll = _polls.find(p => p.id === pollId);
  if (poll) poll.status = "closed";
  renderPolls();
  showToast("Poll closed.", "🔒");
}

/* ── Admin: delete poll ─────────────────────────────────────────────────── */
async function deletePoll(pollId) {
  if (!confirm("Delete this poll and all its votes? This cannot be undone.")) return;
  showLoading(true);
  const res = await apiFetch(`/api/polls/${pollId}`, "DELETE");
  showLoading(false);
  if (!res.success) return showToast(res.message, "❌");

  _polls = _polls.filter(p => p.id !== pollId);
  _updateStats();
  renderPolls();
  showToast("Poll deleted.", "🗑️");
}

/* ── Create poll modal ──────────────────────────────────────────────────── */
function openModal()  { document.getElementById("createModal").classList.remove("hidden"); }
function closeModal() { document.getElementById("createModal").classList.add("hidden"); }
function closeModalOutside(e) {
  if (e.target === document.getElementById("createModal")) closeModal();
}

function addOpt() {
  const list = document.getElementById("optionsList");
  const div  = document.createElement("div");
  div.className = "opt-row";
  div.innerHTML = `<input type="text" class="opt-input" placeholder="Option" /><button class="btn-x" onclick="removeOpt(this)">×</button>`;
  list.appendChild(div);
}

function removeOpt(btn) {
  const rows = document.querySelectorAll("#optionsList .opt-row");
  if (rows.length <= 2) return showToast("Minimum 2 options required.", "⚠️");
  btn.closest(".opt-row").remove();
}

async function submitPoll() {
  const question = document.getElementById("newQ").value.trim();
  const desc     = document.getElementById("newDesc").value.trim();
  const status   = document.getElementById("newStatus").value;
  const options  = [...document.querySelectorAll(".opt-input")]
    .map(i => i.value.trim()).filter(Boolean);

  if (!question)          return showToast("Enter the poll question.", "⚠️");
  if (options.length < 2) return showToast("Add at least 2 options.", "⚠️");

  showLoading(true);
  const res = await apiFetch("/api/polls", "POST", { question, description: desc, options, status });
  showLoading(false);

  if (!res.success) return showToast(res.message, "❌");

  _polls.unshift(res.data.poll);
  closeModal();
  _resetCreateForm();
  _updateStats();
  renderPolls();
  showToast("Poll created! 🎉", "✅");
}

function _resetCreateForm() {
  document.getElementById("newQ").value    = "";
  document.getElementById("newDesc").value = "";
  document.getElementById("optionsList").innerHTML = `
    <div class="opt-row"><input type="text" class="opt-input" placeholder="Option A"/><button class="btn-x" onclick="removeOpt(this)">×</button></div>
    <div class="opt-row"><input type="text" class="opt-input" placeholder="Option B"/><button class="btn-x" onclick="removeOpt(this)">×</button></div>`;
}

