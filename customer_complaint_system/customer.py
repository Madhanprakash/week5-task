"""Customer-facing pages: home, submit complaint, track complaint."""
from __future__ import annotations

import html
import re

import streamlit as st

import database as db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{6,17}$")

STATUS_CLASS = {
    "Open": "b-blue", "Assigned": "b-indigo", "In Progress": "b-amber",
    "Pending Customer Response": "b-orange", "Resolved": "b-green",
    "Closed": "b-grey", "Reopened": "b-red",
}
PRIORITY_CLASS = {"Low": "b-grey", "Medium": "b-blue", "High": "b-orange", "Critical": "b-red"}


def badge(text: str, kind: dict) -> str:
    return f'<span class="badge {kind.get(text, "b-grey")}">{text}</span>'


def go(page: str) -> None:
    st.session_state["page"] = page
    st.rerun()


# ------------------------------------------------------------------ home
def _home_stats() -> tuple[int, int, int]:
    """Read-only figures for the hero chips: (total, resolved %, active)."""
    try:
        df = db.all_complaints()
    except Exception:  # noqa: BLE001 - decorative stats must never break the page
        return 0, 0, 0
    if df.empty:
        return 0, 0, 0
    done = int(df["status"].isin(["Resolved", "Closed"]).sum())
    return len(df), round(100 * done / len(df)), len(df) - done


def render_home() -> None:
    total, pct, active = _home_stats()
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-tag"><span class="live-dot"></span> Customer care &middot; we respond fast</div>
          <h1>We're here to <span class="grad">make it right.</span></h1>
          <p>Tell us what went wrong. Our helpdesk team reviews every complaint,
          keeps you updated, and works with you until it is resolved.</p>
          <div class="hero-stats">
            <div class="chip"><div class="chip-label">Complaints handled</div><div class="chip-value">{total}</div></div>
            <div class="chip"><div class="chip-label">Resolved</div><div class="chip-value c-green">{pct}%</div></div>
            <div class="chip"><div class="chip-label">Being worked on</div><div class="chip-value c-amber">{active}</div></div>
            <div class="chip"><div class="chip-label">System</div><div class="chip-value c-cyan"><span class="live-dot"></span>LIVE</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1.2, 3])
    if c1.button("Submit a Complaint  →", type="primary", width="stretch", key="cta_submit"):
        go("complaint")
    if c2.button("Track Complaint", width="stretch", key="cta_track"):
        go("track")

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    steps = [
        ("📝", "01", "Submit", "Fill in a short form describing the issue. Attach a photo or document if it helps."),
        ("🎫", "02", "Get your ID", "You instantly receive a unique Complaint ID. Keep it to track progress."),
        ("🛠️", "03", "We investigate", "A helpdesk specialist is assigned, reviews the details and takes action."),
        ("✅", "04", "Resolution", "Track status any time with your Complaint ID and email until it is resolved."),
    ]
    cols = st.columns(4)
    for i, (col, (icon, n, title, text)) in enumerate(zip(cols, steps)):
        col.markdown(
            f'<div class="card step" style="animation-delay:{i * 90}ms">'
            f'<div class="step-top"><div class="step-icon">{icon}</div><div class="step-n">{n}</div></div>'
            f'<div class="step-title">{title}</div><div class="muted">{text}</div></div>',
            unsafe_allow_html=True)

    st.markdown('<div class="section-title">Our promise</div>', unsafe_allow_html=True)
    promises = [("⚡", "Fast response", "Every complaint is reviewed by a real person."),
                ("🔒", "Private & secure", "Your details are only used to resolve your case."),
                ("📡", "Live tracking", "Follow every update with just your ID and email.")]
    for col, (icon, title, text) in zip(st.columns(3), promises):
        col.markdown(f'<div class="promise"><div class="promise-icon">{icon}</div>'
                     f'<div><b>{title}</b><div class="muted">{text}</div></div></div>',
                     unsafe_allow_html=True)


# ------------------------------------------------------------- complaint
def validate(name, email, phone, category, subject, description) -> list[str]:
    errors = []
    if len(name.strip()) < 2:
        errors.append("Customer name is required (at least 2 characters).")
    if not EMAIL_RE.match(email.strip()):
        errors.append("Enter a valid email address.")
    if not PHONE_RE.match(phone.strip()):
        errors.append("Enter a valid phone number (7-15 digits, may start with +).")
    if not category:
        errors.append("Select a complaint category.")
    if len(subject.strip()) < 5:
        errors.append("Subject is required (at least 5 characters).")
    if len(description.strip()) < 20:
        errors.append("Description must be at least 20 characters so we can help you.")
    return errors


def render_complaint() -> None:
    st.markdown('<div class="page-title">📝 Submit a <span class="grad">Complaint</span></div>'
                '<div class="muted">Fields marked <span class="req">*</span> are required.</div>',
                unsafe_allow_html=True)

    done = st.session_state.get("submitted_id")
    if done:
        st.markdown(
            f'<div class="card success-card"><div class="success-icon">✓</div>'
            f'<div class="step-title">Complaint submitted successfully</div>'
            f'<div class="muted">Your Complaint ID</div>'
            f'<div class="cid">{done}</div>'
            f'<div class="muted">Save this ID. You will need it with your email to track progress.</div>'
            f'</div>', unsafe_allow_html=True)
        a, b, _ = st.columns([1, 1, 3])
        if a.button("Track this complaint", type="primary", width="stretch"):
            st.session_state["track_prefill"] = done
            st.session_state.pop("submitted_id", None)
            go("track")
        if b.button("Submit another", width="stretch"):
            st.session_state.pop("submitted_id", None)
            st.rerun()
        return

    with st.form("complaint_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer Name *", placeholder="Jane Doe")
        email = c2.text_input("Email Address *", placeholder="jane@example.com")
        c3, c4 = st.columns(2)
        phone = c3.text_input("Phone Number *", placeholder="+91 98765 43210")
        category = c4.selectbox("Complaint Category *", db.CATEGORIES, index=None,
                                placeholder="Select a category")
        subject = st.text_input("Subject *", placeholder="Short summary of the problem", max_chars=120)
        description = st.text_area("Complaint Description *", height=170, max_chars=3000,
                                   placeholder="What happened? Include order numbers, dates and what you expected.")
        upload = st.file_uploader("Attachment (optional)", type=[e.strip(".") for e in db.ALLOWED_EXT],
                                  help="PNG, JPG, PDF or TXT, up to 5 MB.")
        submitted = st.form_submit_button("Submit Complaint", type="primary")

    if not submitted:
        return

    errors = validate(name, email, phone, category, subject, description)
    attachment = None
    if upload is not None:
        if upload.size > db.MAX_UPLOAD_BYTES:
            errors.append("Attachment is larger than 5 MB.")
        else:
            attachment = (upload.name, upload.getvalue())
    if errors:
        for e in errors:
            st.error(e, icon="⚠️")
        return

    try:
        cid = db.create_complaint(name, email, phone, category, subject, description, attachment)
    except db.DuplicateComplaint as dup:
        st.warning(f"This complaint has already been submitted. Your existing Complaint ID is "
                   f"**{dup.complaint_id}**.", icon="ℹ️")
        return
    except Exception as exc:  # noqa: BLE001 - show a friendly error, keep the app alive
        st.error(f"Sorry, we couldn't save your complaint: {exc}")
        return
    st.session_state["submitted_id"] = cid
    st.toast("Complaint submitted", icon="✅")
    st.rerun()


# ----------------------------------------------------------------- track
def render_track() -> None:
    st.markdown('<div class="page-title">📡 Track Your <span class="grad">Complaint</span></div>'
                '<div class="muted">Enter the Complaint ID you received and the email you used.</div>',
                unsafe_allow_html=True)
    prefill = st.session_state.pop("track_prefill", "")
    with st.form("track_form"):
        c1, c2 = st.columns(2)
        cid = c1.text_input("Complaint ID *", value=prefill, placeholder="CMP-2026-AB12CD")
        email = c2.text_input("Email Address *", placeholder="jane@example.com")
        go_btn = st.form_submit_button("Track Status", type="primary")

    if go_btn:
        if not cid.strip() or not email.strip():
            st.error("Enter both the Complaint ID and email address.")
            st.session_state.pop("tracked", None)
        else:
            result = db.track_complaint(cid, email)
            if result is None:
                st.error("No complaint found for that ID and email. Please check both and try again.")
                st.session_state.pop("tracked", None)
            else:
                st.session_state["tracked"] = result

    result = st.session_state.get("tracked")
    if not result:
        return
    c, history = result["complaint"], result["history"]
    # refresh so status changes appear without re-entering details
    fresh = db.track_complaint(c["complaint_id"], c["email"])
    if fresh:
        c, history = fresh["complaint"], fresh["history"]

    st.markdown(
        f'<div class="card"><div class="row-between"><div><div class="muted">{c["complaint_id"]}</div>'
        f'<div class="step-title">{html.escape(c["subject"])}</div></div>{badge(c["status"], STATUS_CLASS)}</div>'
        f'<div class="detail-grid">'
        f'<div><div class="muted">Category</div><b>{html.escape(c["category"])}</b></div>'
        f'<div><div class="muted">Submitted</div><b>{c["created_at"]}</b></div>'
        f'<div><div class="muted">Last update</div><b>{c["updated_at"]}</b></div>'
        f'<div><div class="muted">Handled by</div><b>{html.escape(c["assigned_to"] or "Awaiting assignment")}</b></div>'
        f'</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Updates</div>', unsafe_allow_html=True)
    for h in history:
        who = "You" if h["actor"] == "Customer" else html.escape(h["actor"])
        label = "Message from helpdesk" if h["kind"] == "customer" else html.escape(h["note"])
        body = html.escape(h["note"]) if h["kind"] == "customer" else ""
        st.markdown(
            f'<div class="timeline-item"><div class="dot"></div><div>'
            f'<div><b>{label}</b></div>'
            f'{f"<div>{body}</div>" if body else ""}'
            f'<div class="muted">{who} · {h["created_at"]}</div></div></div>',
            unsafe_allow_html=True)
