"""BrightCart AI Customer Support Desk: Streamlit UI.

Run with:  streamlit run app.py
"""
import asyncio
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from agents.ticket_store import LOG_FILE, read_tickets, update_ticket_status
from team import run_ticket

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BrightCart Support",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────
HELPDESK_USER     = os.getenv("HELPDESK_USER", "helpdesk")
HELPDESK_PASS     = os.getenv("HELPDESK_PASS", "support123")
OPENAI_MODEL      = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

ALL_STATUSES      = ["Escalated", "Open", "In Progress", "Resolved", "Closed"]

AGENT_INFO = {
    "QueryAgent":      ("🔎", "Query",      "Reads the complaint — category, urgency, mood"),
    "KnowledgeAgent":  ("📚", "Knowledge",  "Searches company policy documents"),
    "ResolutionAgent": ("✍️", "Resolution", "Writes the reply from policy facts only"),
    "LogAgent":        ("🗂️", "Log",        "Saves the ticket and applies escalation rules"),
}

SAMPLES = {
    "Late delivery":   "Where is my order? It was supposed to arrive yesterday.",
    "Refund request":  "I want to return the shoes I bought last week. How do I get a refund?",
    "Password reset":  "I forgot my password and can't log in.",
    "Broken item":     "The blender I received is broken. Can I get a replacement?",
    "Billing + legal": "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer.",
    "Out-of-policy":   "Do you sell gift cards for a company of 500 employees with custom branding?",
}

STATUS_STYLE = {
    "Escalated":   ("#fee2e2", "#991b1b", "🔴"),
    "Open":        ("#dbeafe", "#1e40af", "🔵"),
    "In Progress": ("#fef9c3", "#854d0e", "🟡"),
    "Resolved":    ("#dcfce7", "#166534", "🟢"),
    "Closed":      ("#f1f5f9", "#475569", "⚫"),
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
header { visibility: hidden; }

.main .block-container { padding-top: 0; padding-bottom: 2rem; max-width: 1200px; }

/* ── Top bar ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0 0.75rem;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 1.5rem;
}
.brand-name  { font-size: 1.2rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em; }
.brand-badge {
    display: inline-block;
    background: #dbeafe; color: #1e40af;
    font-size: 0.7rem; font-weight: 700;
    padding: 0.15rem 0.5rem; border-radius: 999px;
    letter-spacing: 0.05em; text-transform: uppercase;
    margin-left: 0.4rem; vertical-align: middle;
}

/* ── Metric tiles ── */
[data-testid="metric-container"] {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04);
    transition: box-shadow 0.2s;
}
[data-testid="metric-container"]:hover { box-shadow: 0 4px 16px rgba(15,23,42,0.08); }
[data-testid="stMetricLabel"]  { font-size: 0.68rem !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.07em !important; color: #64748b !important; }
[data-testid="stMetricValue"]  { font-size: 1.9rem !important; font-weight: 700 !important; color: #0f172a !important; line-height: 1.2 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #e2e8f0; background: transparent; }
.stTabs [data-baseweb="tab"] { height: 42px; padding: 0 1.1rem; font-weight: 500; font-size: 0.875rem; color: #64748b; border-bottom: 2px solid transparent; margin-bottom: -2px; background: transparent !important; }
.stTabs [aria-selected="true"] { color: #2563eb !important; border-bottom-color: #2563eb !important; }

/* ── Forms ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 8px !important; border: 1.5px solid #e2e8f0 !important; font-size: 0.875rem !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    border: none !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 0.875rem !important;
}
.stButton > button { border-radius: 8px !important; font-weight: 500 !important; font-size: 0.875rem !important; }

/* ── Customer hero ── */
.hero-heading { font-size: 2rem; font-weight: 700; letter-spacing: -0.03em; color: #0f172a; margin-bottom: 0.4rem; }
.hero-sub     { font-size: 1rem; color: #64748b; margin-bottom: 1.75rem; }

/* ── Confirmation card ── */
.confirm-card {
    background: #f0fdf4; border: 1px solid #86efac; border-radius: 12px;
    padding: 1.5rem 1.75rem; margin-bottom: 1.25rem;
}
.confirm-title { font-size: 1.1rem; font-weight: 700; color: #166534; margin-bottom: 0.4rem; }
.confirm-id    { font-size: 1.5rem; font-weight: 800; color: #15803d; letter-spacing: -0.02em; }
.confirm-sub   { font-size: 0.85rem; color: #4ade80; color: #166534; margin-top: 0.5rem; }

/* ── Login card ── */
.login-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 2rem; box-shadow: 0 4px 24px rgba(15,23,42,0.08); }
.login-title { font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-bottom: 0.25rem; text-align: center; }
.login-sub   { font-size: 0.8rem; color: #64748b; text-align: center; margin-bottom: 1.25rem; }

/* ── Helpdesk ticket detail ── */
.detail-header { font-size: 0.95rem; font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; }
.detail-row    { display: flex; gap: 0.6rem; align-items: baseline; font-size: 0.85rem; margin-bottom: 0.3rem; }
.detail-key    { font-weight: 600; color: #475569; min-width: 120px; }
.detail-val    { color: #1e293b; }

/* ── Status badge ── */
.sbadge {
    display: inline-block; padding: 0.18rem 0.6rem;
    border-radius: 999px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
}

/* ── Agent step ── */
.agent-step { background: #f8fafc; border: 1px solid #e8f0fe; border-left: 3px solid #2563eb; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; }
.agent-step-title { font-weight: 600; color: #1e293b; }
.agent-step-desc  { color: #64748b; font-size: 0.78rem; font-style: italic; }

/* ── Misc ── */
[data-testid="stExpander"]       { border: 1px solid #e2e8f0 !important; border-radius: 10px !important; }
[data-testid="stDataFrame"]      { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
[data-testid="stDownloadButton"] button { border-radius: 8px !important; font-size: 0.85rem !important; }

/* ── Dark mode ── */
@media (prefers-color-scheme: dark) {
    .brand-name  { color: #f1f5f9; }
    .hero-heading { color: #f1f5f9; }
    [data-testid="metric-container"] { background: #1e293b; border-color: #334155; box-shadow: none; }
    [data-testid="stMetricLabel"]    { color: #94a3b8 !important; }
    [data-testid="stMetricValue"]    { color: #f8fafc !important; }
    .detail-key  { color: #94a3b8; }
    .detail-val  { color: #e2e8f0; }
    .agent-step  { background: #1e293b; border-color: #334155; border-left-color: #3b82f6; }
    .agent-step-title { color: #f1f5f9; }
    .login-card  { background: #1e293b; border-color: #334155; }
    .login-title { color: #f1f5f9; }
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
for _k, _v in {
    "logged_in":          False,
    "show_login":         False,
    "selected_ticket_id": None,
    "last_submission_id": None,
    "complaint":          "",
    "login_error":        "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Shared helpers ────────────────────────────────────────────────────────────
def status_badge(status: str) -> str:
    bg, color, emoji = STATUS_STYLE.get(status, ("#f1f5f9", "#475569", "⚪"))
    return (
        f'<span class="sbadge" style="background:{bg};color:{color};">'
        f'{emoji} {status}</span>'
    )


def render_bar_chart(series: pd.Series, title: str) -> None:
    if _PLOTLY and not series.empty:
        df = series.value_counts().reset_index()
        df.columns = ["label", "count"]
        fig = px.bar(df, x="label", y="count", text="count",
                     color_discrete_sequence=["#3b82f6"])
        fig.update_traces(textposition="outside", marker_line_width=0, textfont_size=11)
        fig.update_layout(
            title=dict(text=title, font_size=13, font_color="#1e293b"),
            xaxis=dict(title="", showgrid=False, tickfont_size=11),
            yaxis=dict(title="", showgrid=True, gridcolor="#f1f5f9",
                       tickfont_size=11, rangemode="tozero"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_family="Inter, sans-serif", margin=dict(l=0, r=0, t=28, b=0),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(f"**{title}**")
        st.bar_chart(series.value_counts())


def render_donut_chart(series: pd.Series, title: str,
                       color_map: dict | None = None) -> None:
    if _PLOTLY and not series.empty:
        df = series.value_counts().reset_index()
        df.columns = ["label", "count"]
        colors = [color_map.get(l, "#3b82f6") for l in df["label"]] if color_map else None
        fig = go.Figure(go.Pie(
            labels=df["label"], values=df["count"],
            hole=0.55, marker_colors=colors,
            textinfo="percent+label", textfont_size=11,
        ))
        fig.update_layout(
            title=dict(text=title, font_size=13, font_color="#1e293b"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_family="Inter, sans-serif", margin=dict(l=0, r=0, t=28, b=0),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(f"**{title}**")
        st.bar_chart(series.value_counts())


# ── Top bar ───────────────────────────────────────────────────────────────────
_tb_left, _tb_space, _tb_right = st.columns([4, 2, 1])

with _tb_left:
    if st.session_state.logged_in:
        st.markdown(
            '<span class="brand-name">🛒 BrightCart</span>'
            '<span class="brand-badge">Helpdesk</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<span class="brand-name">🛒 BrightCart Support</span>',
                    unsafe_allow_html=True)

with _tb_right:
    if st.session_state.logged_in:
        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.logged_in          = False
            st.session_state.show_login         = False
            st.session_state.selected_ticket_id = None
            st.rerun()
    else:
        _lbl = "✕ Cancel" if st.session_state.show_login else "Helpdesk Login"
        if st.button(_lbl, key="login_btn", use_container_width=True):
            st.session_state.show_login  = not st.session_state.show_login
            st.session_state.login_error = ""
            st.rerun()

st.markdown('<hr style="border-color:#e2e8f0;margin:0 0 1.5rem;">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN FORM
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_login and not st.session_state.logged_in:
    _, col, _ = st.columns([2, 1, 2])
    with col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Helpdesk Login</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Enter your credentials to access the support desk</div>',
                    unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="e.g. helpdesk")
            password = st.text_input("Password", type="password")
            if st.session_state.login_error:
                st.error(st.session_state.login_error)
            ok = st.form_submit_button("Sign in", type="primary", use_container_width=True)

        if ok:
            if username == HELPDESK_USER and password == HELPDESK_PASS:
                st.session_state.logged_in   = True
                st.session_state.show_login  = False
                st.session_state.login_error = ""
                st.rerun()
            else:
                st.session_state.login_error = "Incorrect username or password."
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER PAGE
# ══════════════════════════════════════════════════════════════════════════════
elif not st.session_state.logged_in:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        # ── Confirmation after submission ──
        if st.session_state.last_submission_id:
            tid = st.session_state.last_submission_id
            st.markdown(
                f'<div class="confirm-card">'
                f'<div class="confirm-title">✅ Complaint received!</div>'
                f'<div class="confirm-id">{tid}</div>'
                f'<div class="confirm-sub">'
                f'Our AI support team has reviewed your complaint and prepared a response. '
                f'A member of our team will follow up if further action is needed.'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("Submit another complaint", key="new_complaint_btn"):
                st.session_state.last_submission_id = None
                st.session_state["complaint"]       = ""
                st.rerun()

        # ── Submission form ──
        else:
            st.markdown('<div class="hero-heading">How can we help you?</div>',
                        unsafe_allow_html=True)
            st.markdown('<div class="hero-sub">Submit your complaint and our support team will be in touch.</div>',
                        unsafe_allow_html=True)

            # Sample loader
            s_col, b_col = st.columns([3, 1])
            sample_choice = s_col.selectbox("Sample", list(SAMPLES), index=0,
                                            label_visibility="collapsed")
            if b_col.button("Try a sample", key="load_sample", use_container_width=True):
                st.session_state["complaint"] = SAMPLES[sample_choice]
                st.rerun()

            with st.form("customer_form", clear_on_submit=False):
                n_col, o_col = st.columns(2)
                customer_name = n_col.text_input("Your name (optional)", placeholder="e.g. Priya")
                order_id      = o_col.text_input("Order ID (optional)",  placeholder="e.g. ORD-4512")
                complaint = st.text_area(
                    "Describe your issue",
                    key="complaint",
                    height=150,
                    placeholder="Tell us what happened in as much detail as you can…",
                )
                cc, sc = st.columns([3, 1])
                cc.caption(f"{len(complaint)} characters")
                submitted = sc.form_submit_button("Submit Complaint", type="primary",
                                                  use_container_width=True)

            if submitted:
                if len(complaint.strip()) < 10:
                    st.warning("Please describe your issue in at least 10 characters.")
                else:
                    with st.spinner("Reviewing your complaint — this takes a few seconds…"):
                        try:
                            result = asyncio.run(
                                run_ticket(customer_name, order_id, complaint)
                            )
                            st.session_state.last_submission_id = result["ticket_id"]
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not process your complaint: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# HELPDESK DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
else:
    tickets = read_tickets()
    df_all  = pd.DataFrame(tickets) if tickets else pd.DataFrame(
        columns=["ticket_id", "timestamp", "customer_name", "order_id",
                 "complaint", "category", "urgency", "sentiment", "summary",
                 "kb_sources", "response", "confidence", "status", "escalation_reason"]
    )

    # ── Stats ──
    total      = len(df_all)
    escalated  = int((df_all["status"] == "Escalated").sum())  if total else 0
    open_c     = int((df_all["status"] == "Open").sum())        if total else 0
    in_prog    = int((df_all["status"] == "In Progress").sum()) if total else 0
    resolved   = int((df_all["status"] == "Resolved").sum())    if total else 0
    closed     = int((df_all["status"] == "Closed").sum())      if total else 0

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total tickets",  total)
    s2.metric("🔴 Escalated",   escalated)
    s3.metric("🔵 Open",        open_c)
    s4.metric("🟡 In Progress", in_prog)
    s5.metric("🟢 Resolved",    resolved)

    st.write("")

    tab_tickets, tab_insights = st.tabs(["📋  All Tickets", "📊  Insights"])

    # ── Tab 1: Ticket management ──────────────────────────────────────────────
    with tab_tickets:
        if df_all.empty:
            st.info("No tickets yet. Customers can submit complaints on the main page.")
        else:
            # Filters
            f1, f2, f3 = st.columns([1, 2, 2])
            status_filter   = f1.selectbox("Status", ["All"] + ALL_STATUSES)
            category_filter = f2.multiselect("Category",
                                             sorted(df_all["category"].dropna().unique()))
            search_text     = f3.text_input("Search", placeholder="Customer name, order ID, or keyword…")

            filtered = df_all.copy()
            if status_filter != "All":
                filtered = filtered[filtered["status"] == status_filter]
            if category_filter:
                filtered = filtered[filtered["category"].isin(category_filter)]
            if search_text.strip():
                q    = search_text.strip()
                mask = (
                    filtered["complaint"].str.contains(q, case=False, na=False)
                    | filtered["customer_name"].str.contains(q, case=False, na=False)
                    | filtered["order_id"].str.contains(q, case=False, na=False)
                    | filtered["response"].str.contains(q, case=False, na=False)
                )
                filtered = filtered[mask]

            st.caption(f"Showing **{len(filtered)}** of **{total}** tickets")

            # Table
            DISPLAY = ["ticket_id", "timestamp", "customer_name", "order_id",
                       "category", "urgency", "status", "summary"]
            st.dataframe(
                filtered[DISPLAY],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "ticket_id":     st.column_config.TextColumn("Ticket ID",  width="small"),
                    "timestamp":     st.column_config.TextColumn("Time",       width="medium"),
                    "customer_name": st.column_config.TextColumn("Customer",   width="small"),
                    "order_id":      st.column_config.TextColumn("Order",      width="small"),
                    "category":      st.column_config.TextColumn("Category",   width="small"),
                    "urgency":       st.column_config.TextColumn("Urgency",    width="small"),
                    "status":        st.column_config.TextColumn("Status",     width="small"),
                    "summary":       st.column_config.TextColumn("Summary"),
                },
            )

            # Ticket selector
            if not filtered.empty:
                st.markdown("---")
                st.markdown("**Select a ticket to review**")
                chosen_id = st.selectbox(
                    "Ticket", filtered["ticket_id"].tolist(),
                    index=0, label_visibility="collapsed",
                    key="ticket_selector",
                )

                ticket = next(
                    (t for t in tickets if t["ticket_id"] == chosen_id), None
                )
                if ticket:
                    st.markdown(f"### {chosen_id}")

                    # ── Status update card ───────────────────────────────
                    bg, fg, emoji = STATUS_STYLE.get(
                        ticket["status"], ("#f1f5f9", "#475569", "⚪")
                    )
                    st.markdown(
                        f'<div style="background:{bg};border:1px solid {fg}33;border-radius:10px;'
                        f'padding:1rem 1.25rem;margin-bottom:1rem;">'
                        f'<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:0.07em;color:{fg};margin-bottom:0.5rem;">Current status</div>'
                        f'<span class="sbadge" style="background:{bg};color:{fg};font-size:0.85rem;">'
                        f'{emoji} {ticket["status"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    u_col, b_col = st.columns([2, 1])
                    new_status = u_col.selectbox(
                        "Update status to",
                        ALL_STATUSES,
                        index=ALL_STATUSES.index(ticket["status"])
                              if ticket["status"] in ALL_STATUSES else 0,
                        key=f"status_sel_{chosen_id}",
                    )
                    b_col.write("")          # vertical alignment nudge
                    b_col.write("")
                    if b_col.button("Update Status", key=f"update_btn_{chosen_id}",
                                    use_container_width=True, type="primary"):
                        if update_ticket_status(chosen_id, new_status):
                            st.toast(f"{chosen_id} status updated to {new_status}", icon="✅")
                            st.rerun()
                        else:
                            st.error("Could not update status. Ticket not found.")

                    # ── Ticket details ───────────────────────────────────
                    st.markdown("**Ticket details**")
                    pairs = [
                        ("Ticket ID",        ticket["ticket_id"]),
                        ("Logged at",        ticket["timestamp"]),
                        ("Customer",         ticket["customer_name"] or "Not given"),
                        ("Order ID",         ticket["order_id"]      or "Not given"),
                        ("Category",         ticket["category"]      or "—"),
                        ("Urgency",          ticket["urgency"]       or "—"),
                        ("Sentiment",        ticket["sentiment"]     or "—"),
                        ("Confidence",       ticket["confidence"]    or "—"),
                        ("Knowledge source", ticket["kb_sources"]    or "None found"),
                    ]
                    for key, val in pairs:
                        st.markdown(
                            f'<div class="detail-row">'
                            f'<span class="detail-key">{key}</span>'
                            f'<span class="detail-val">{val}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    if ticket.get("escalation_reason"):
                        st.warning(f"**Escalation reason:** {ticket['escalation_reason']}")

                    st.markdown("**Summary**")
                    st.info(ticket["summary"])

                    st.markdown("**AI-generated reply**")
                    st.info(ticket["response"])
                    st.code(ticket["response"], language=None)

                    with st.expander("Original complaint"):
                        st.write(ticket["complaint"])

            # ── Downloads ──
            st.write("")
            d1, d2 = st.columns(2)
            d1.download_button(
                "⬇  Download filtered view (CSV)",
                data=filtered.to_csv(index=False).encode("utf-8") if not filtered.empty else b"",
                file_name="tickets_filtered.csv",
                mime="text/csv",
                disabled=filtered.empty,
            )
            d2.download_button(
                "⬇  Download full log (CSV)",
                data=LOG_FILE.read_bytes() if LOG_FILE.exists() else b"",
                file_name="tickets_all.csv",
                mime="text/csv",
                disabled=not LOG_FILE.exists(),
            )

    # ── Tab 2: Insights ───────────────────────────────────────────────────────
    with tab_insights:
        if df_all.empty:
            st.info("Charts appear once tickets have been logged.")
        else:
            r1, r2 = st.columns(2)
            with r1:
                render_bar_chart(df_all["category"], "Complaints by category")
            with r2:
                render_bar_chart(df_all["urgency"],  "Urgency breakdown")

            r3, r4 = st.columns(2)
            with r3:
                render_donut_chart(
                    df_all["status"], "Ticket status distribution",
                    color_map={
                        "Resolved":    "#22c55e",
                        "Escalated":   "#ef4444",
                        "Open":        "#3b82f6",
                        "In Progress": "#eab308",
                        "Closed":      "#94a3b8",
                    },
                )
            with r4:
                reasons = (
                    df_all.loc[df_all["escalation_reason"].str.strip().ne(""), "escalation_reason"]
                    .str.split("; ").explode().dropna()
                )
                if reasons.empty:
                    st.info("No escalation data yet.")
                else:
                    render_bar_chart(reasons, "Escalation reasons")

            st.write("")
            render_bar_chart(df_all["sentiment"], "Customer sentiment")
