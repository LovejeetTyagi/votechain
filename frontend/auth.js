/* ─── auth.js — VoteChain frontend authentication ─────────────────────────
   Handles:
     • Tab switching (login / register)
     • 2-step OTP flow for both login and registration
     • JWT storage in localStorage
     • logout()
   All API calls go through apiFetch() defined at the bottom.
   ─────────────────────────────────────────────────────────────────────────── */

const API_BASE = "";          // Empty = same origin. Change to http://localhost:5000 in dev

/* ── State ─────────────────────────────────────────────────────────────── */
let loginStep   = 1;          // 1 = waiting for email  |  2 = waiting for OTP
let regStep     = 1;

/* ── Tab switching ──────────────────────────────────────────────────────── */
function switchTab(tab) {
  loginStep = 1;
  regStep   = 1;
  _resetForms();

  document.querySelectorAll(".auth-tab").forEach((el, i) => {
    el.classList.toggle("active", (i === 0 && tab === "login") || (i === 1 && tab === "register"));
  });
  document.getElementById("tabLogin").style.display    = tab === "login"    ? "" : "none";
  document.getElementById("tabRegister").style.display = tab === "register" ? "" : "none";
}

function _resetForms() {
  ["loginEmail","loginOtp","regName","regEmail","regOtp"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  document.getElementById("loginOtpSection").style.display = "none";
  document.getElementById("regOtpSection").style.display   = "none";
  document.getElementById("loginBtn").textContent = "Send OTP →";
  document.getElementById("regBtn").textContent   = "Send OTP →";
}

/* ── LOGIN flow ─────────────────────────────────────────────────────────── */
async function loginFlow() {
  if (loginStep === 1) {
    const email = document.getElementById("loginEmail").value.trim();
    if (!_validEmail(email)) return showToast("Enter a valid email.", "⚠️");

    showLoading(true);
    const res = await apiFetch("/api/auth/login/send-otp", "POST", { email });
    showLoading(false);

    if (!res.success) return showToast(res.message, "❌");

    loginStep = 2;
    document.getElementById("loginOtpSection").style.display = "";
    document.getElementById("loginBtn").textContent = "Verify & Sign in →";
    showToast("OTP sent! Check your inbox.", "📨");

  } else {
    const email = document.getElementById("loginEmail").value.trim();
    const otp   = document.getElementById("loginOtp").value.trim();
    if (!otp || otp.length !== 6) return showToast("Enter the 6-digit OTP.", "⚠️");

    showLoading(true);
    const res = await apiFetch("/api/auth/login/verify-otp", "POST", { email, otp });
    showLoading(false);

    if (!res.success) return showToast(res.message, "❌");

    _saveSession(res.data.token, res.data.user);
    enterDashboard(res.data.user);
  }
}

/* ── REGISTER flow ──────────────────────────────────────────────────────── */
async function registerFlow() {
  if (regStep === 1) {
    const name  = document.getElementById("regName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const role  = document.getElementById("regRole").value;

    if (!name)              return showToast("Name is required.", "⚠️");
    if (!_validEmail(email)) return showToast("Enter a valid email.", "⚠️");

    showLoading(true);
    const res = await apiFetch("/api/auth/register/send-otp", "POST", { name, email, role });
    showLoading(false);

    if (!res.success) return showToast(res.message, "❌");

    regStep = 2;
    document.getElementById("regOtpSection").style.display = "";
    document.getElementById("regBtn").textContent = "Verify & Create Account →";
    showToast("OTP sent! Check your inbox.", "📨");

  } else {
    const email = document.getElementById("regEmail").value.trim();
    const otp   = document.getElementById("regOtp").value.trim();
    if (!otp || otp.length !== 6) return showToast("Enter the 6-digit OTP.", "⚠️");

    showLoading(true);
    const res = await apiFetch("/api/auth/register/verify-otp", "POST", { email, otp });
    showLoading(false);

    if (!res.success) return showToast(res.message, "❌");

    _saveSession(res.data.token, res.data.user);
    enterDashboard(res.data.user);
  }
}

/* ── Logout ─────────────────────────────────────────────────────────────── */
function logout() {
  localStorage.removeItem("vc_token");
  localStorage.removeItem("vc_user");
  location.reload();
}

/* ── Session helpers ────────────────────────────────────────────────────── */
function _saveSession(token, user) {
  localStorage.setItem("vc_token", token);
  localStorage.setItem("vc_user",  JSON.stringify(user));
}

function getToken()    { return localStorage.getItem("vc_token"); }
function getCurrentUser() {
  try { return JSON.parse(localStorage.getItem("vc_user")); }
  catch { return null; }
}

/* ── Auto-restore session on page load ──────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  const token = getToken();
  const user  = getCurrentUser();
  if (token && user) {
    enterDashboard(user);
  }
});

/* ── Validation helpers ─────────────────────────────────────────────────── */
function _validEmail(email) {
  return email && email.includes("@") && email.includes(".");
}

/* ─────────────────────────────────────────────────────────────────────────
   apiFetch — central fetch wrapper
   • Automatically attaches Authorization: Bearer <token>
   • Returns parsed JSON (or error object on network failure)
   ───────────────────────────────────────────────────────────────────────── */
async function apiFetch(path, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  const token   = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res  = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json();
    return data;
  } catch (err) {
    console.error("apiFetch error:", err);
    return { success: false, message: "Network error. Is the server running?" };
  }
}

/* ─────────────────────────────────────────────────────────────────────────
   UI helpers  (toast, loading overlay)
   ───────────────────────────────────────────────────────────────────────── */
let _toastTimer;
function showToast(msg, icon = "✓") {
  const t = document.getElementById("toast");
  document.getElementById("toastMsg").textContent  = msg;
  document.getElementById("toastIcon").textContent = icon;
  t.classList.remove("hidden");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.add("hidden"), 3500);
}

function showLoading(show) {
  document.getElementById("loadingOverlay").classList.toggle("hidden", !show);
}
