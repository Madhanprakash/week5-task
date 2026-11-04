"""BrightCart Customer Complaint Management System: entry point & router.

Run:  streamlit run app.py
"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="BrightCart Complaints", page_icon="🛒", layout="wide",
                   initial_sidebar_state="auto")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

import auth  # noqa: E402
import customer  # noqa: E402
import database as db  # noqa: E402
import helpdesk  # noqa: E402

HERE = Path(__file__).parent


@st.cache_resource
def bootstrap() -> bool:
    """Create schema, helpdesk users and sample data once per server process."""
    db.init_db()
    auth.seed_users()
    db.seed_sample_data()
    return True


def load_css() -> None:
    css = (HERE / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def top_bar(page: str, user: dict | None) -> None:
    left, right = st.columns([5, 1.2])
    left.markdown('<div class="brand"><span class="brand-logo">🛒</span>'
                  '<span class="brand-name">BrightCart</span>'
                  '<span class="brand-sub">Complaint Center</span></div>', unsafe_allow_html=True)
    with right:
        if user:
            if st.button("Open Helpdesk", key="top_hd", type="primary", width="stretch"):
                customer.go("helpdesk")
        elif page != "login":
            if st.button("Login", key="top_login", type="primary", width="stretch"):
                customer.go("login")
        else:
            if st.button("← Back", key="top_back", width="stretch"):
                customer.go("home")


def render_login() -> None:
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<div class="login-card"><div class="login-icon">🔐</div>'
                    '<div class="page-title" style="text-align:center">Helpdesk Login</div>'
                    '<div class="muted" style="text-align:center">Authorised BrightCart staff only.</div>'
                    '</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            ident = st.text_input("Username or email", autocomplete="username")
            pw = st.text_input("Password", type="password", autocomplete="current-password")
            go = st.form_submit_button("Sign in", type="primary", width="stretch")
        if go:
            ok, msg = auth.login(ident, pw)
            if ok:
                st.session_state["page"] = "helpdesk"
                st.session_state["hd_page"] = "Dashboard"
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.error(msg)


def main() -> None:
    bootstrap()
    load_css()
    st.session_state.setdefault("page", "home")
    user = auth.current_user()
    page = st.session_state["page"]

    # Access control: the helpdesk area is only reachable when authenticated.
    if page == "helpdesk" and not user:
        page = st.session_state["page"] = "login"
    if page == "login" and user:
        page = st.session_state["page"] = "helpdesk"

    if page == "helpdesk":
        helpdesk.render_helpdesk()
        return

    top_bar(page, user)
    if page == "complaint":
        customer.render_complaint()
    elif page == "track":
        customer.render_track()
    elif page == "login":
        render_login()
    else:
        customer.render_home()

    if page in ("complaint", "track"):
        st.write("")
        if st.button("← Back to home", key="back_home"):
            customer.go("home")
    st.markdown('<div class="footer">© BrightCart · Customer Complaint Center</div>',
                unsafe_allow_html=True)


main()
