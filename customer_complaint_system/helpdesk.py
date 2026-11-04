"""Helpdesk area: sidebar navigation, complaint list, filters and complaint detail."""
from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import auth
import database as db
from customer import PRIORITY_CLASS, STATUS_CLASS, badge
from dashboard import render_dashboard

PAGES = {"Dashboard": "📊", "Complaints": "🗂️"}
CONFIRM_STATUSES = {"Resolved", "Closed", "Reopened"}
KIND_LABEL = {"created": "Submitted", "status": "Status", "assignment": "Assignment",
              "priority": "Priority", "internal": "Internal note",
              "customer": "Customer remark", "action": "Action taken"}


def esc(value) -> str:
    return html.escape(str(value or ""))


# -------------------------------------------------------------- shell
def render_helpdesk() -> None:
    user = auth.current_user()
    page = st.session_state.setdefault("hd_page", "Dashboard")
    with st.sidebar:
        st.markdown('<div class="side-brand">🛒 BrightCart<span>Helpdesk</span></div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="side-user"><b>{esc(user["name"])}</b>'
                    f'<div>{esc(user["role"]).title()}</div></div>', unsafe_allow_html=True)
        for name, icon in PAGES.items():
            if st.button(f"{icon}  {name}", key=f"nav_{name}", width="stretch",
                         type="primary" if page == name else "secondary"):
                st.session_state["hd_page"] = name
                st.rerun()
        st.divider()
        if st.button("↩  Log out", key="logout_btn", width="stretch"):
            auth.logout()
            st.rerun()

    if page == "Dashboard":
        render_dashboard()
    else:
        render_complaints()


# ----------------------------------------------------------- complaints
def _filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        cid = c1.text_input("Complaint ID", placeholder="CMP-2026-…", key="f_id")
        cust = c2.text_input("Customer name", placeholder="Search name", key="f_name")
        cat = c3.multiselect("Category", db.CATEGORIES, key="f_cat")
        c4, c5, c6 = st.columns(3)
        status = c4.multiselect("Status", db.STATUSES, key="f_status")
        prio = c5.multiselect("Priority", db.PRIORITIES, key="f_prio")
        dates = c6.date_input("Submission date", value=(), key="f_date",
                              help="Pick a start and end date, or leave empty for all.")
    out = df
    if cid.strip():
        out = out[out["complaint_id"].str.contains(cid.strip(), case=False, regex=False)]
    if cust.strip():
        out = out[out["customer_name"].str.contains(cust.strip(), case=False, regex=False)]
    if cat:
        out = out[out["category"].isin(cat)]
    if status:
        out = out[out["status"].isin(status)]
    if prio:
        out = out[out["priority"].isin(prio)]
    if isinstance(dates, (tuple, list)) and dates:
        start = dates[0]
        end = dates[1] if len(dates) > 1 else dates[0]
        d = pd.to_datetime(out["created_at"]).dt.date
        out = out[(d >= start) & (d <= end)]
    return out


def render_complaints() -> None:
    st.markdown('<div class="page-title">🗂️ Complaint <span class="grad">Management</span></div>'
                '<div class="muted">Search, filter and select a complaint to manage it.</div>',
                unsafe_allow_html=True)
    df = db.all_complaints()
    filtered = _filters(df)

    st.caption(f"{len(filtered)} of {len(df)} complaints")
    view = filtered[["complaint_id", "customer_name", "category", "priority", "status",
                     "assigned_to", "created_at"]].rename(columns={
        "complaint_id": "ID", "customer_name": "Customer", "category": "Category",
        "priority": "Priority", "status": "Status", "assigned_to": "Assigned to",
        "created_at": "Submitted"})
    event = st.dataframe(view, hide_index=True, width="stretch", height=330,
                         on_select="rerun", selection_mode="single-row", key="complaint_table")
    c1, _ = st.columns([1, 4])
    c1.download_button("Export CSV", filtered.drop(columns=["fingerprint"]).to_csv(index=False),
                       file_name=f"complaints_{date.today()}.csv", mime="text/csv",
                       width="stretch", disabled=filtered.empty)

    rows = event.selection.rows if event and event.selection else []
    if rows and rows[0] < len(filtered):
        st.session_state["hd_selected"] = filtered.iloc[rows[0]]["complaint_id"]
    selected = st.session_state.get("hd_selected")
    if not selected:
        st.info("Select a row above to open the complaint details.")
        return
    render_detail(selected)


# --------------------------------------------------------------- detail
def render_detail(cid: str) -> None:
    row = db.get_complaint(cid)
    if row is None:
        st.warning("That complaint no longer exists.")
        st.session_state.pop("hd_selected", None)
        return
    c = dict(row)
    st.markdown("---")
    st.markdown(
        f'<div class="card"><div class="row-between"><div><div class="muted">{esc(c["complaint_id"])}</div>'
        f'<div class="step-title">{esc(c["subject"])}</div></div>'
        f'<div>{badge(c["priority"], PRIORITY_CLASS)} {badge(c["status"], STATUS_CLASS)}</div></div>'
        f'<div class="detail-grid">'
        f'<div><div class="muted">Customer</div><b>{esc(c["customer_name"])}</b></div>'
        f'<div><div class="muted">Email</div><b>{esc(c["email"])}</b></div>'
        f'<div><div class="muted">Phone</div><b>{esc(c["phone"])}</b></div>'
        f'<div><div class="muted">Category</div><b>{esc(c["category"])}</b></div>'
        f'<div><div class="muted">Submitted</div><b>{esc(c["created_at"])}</b></div>'
        f'<div><div class="muted">Assigned to</div><b>{esc(c["assigned_to"]) or "Unassigned"}</b></div>'
        f'</div></div>', unsafe_allow_html=True)

    with st.expander("Complaint description", expanded=True):
        st.write(c["description"])

    atts = db.get_attachments(cid)
    with st.expander(f"Attachments ({len(atts)})", expanded=bool(atts)):
        if not atts:
            st.caption("No files were uploaded.")
        for a in atts:
            p = Path(a["stored_path"])
            if not p.exists():
                st.warning(f"{a['filename']} is missing from disk.")
                continue
            if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                st.image(str(p), caption=a["filename"], width=320)
            st.download_button(f"Download {a['filename']} ({a['size_bytes'] // 1024 or 1} KB)",
                               p.read_bytes(), file_name=a["filename"], key=f"dl_{a['id']}")

    render_actions_form(c)

    with st.expander("Previous actions and comments", expanded=True):
        for a in db.get_actions(cid):
            internal = a["kind"] == "internal"
            st.markdown(
                f'<div class="timeline-item"><div class="dot {"dot-internal" if internal else ""}"></div><div>'
                f'<div><span class="kind">{KIND_LABEL.get(a["kind"], a["kind"])}</span> {esc(a["note"])}</div>'
                f'<div class="muted">{esc(a["actor"])} · {esc(a["created_at"])}</div></div></div>',
                unsafe_allow_html=True)


@st.dialog("Confirm change")
def confirm_dialog(cid: str, pending: dict) -> None:
    st.write(f"Set **{cid}** to **{pending['status']}**? The customer will see this status update.")
    a, b = st.columns(2)
    if a.button("Confirm", type="primary", width="stretch"):
        apply_changes(cid, pending)
        st.session_state["_toast"] = "Complaint updated"
        st.rerun()
    if b.button("Cancel", width="stretch"):
        st.rerun()


def apply_changes(cid: str, p: dict) -> None:
    actor = auth.current_user()["name"]
    try:
        db.update_complaint(cid, actor, status=p["status"], assigned_to=p["assignee"],
                            priority=p["priority"])
        if p["internal"].strip():
            db.add_action(cid, actor, "internal", p["internal"])
        if p["customer"].strip():
            db.add_action(cid, actor, "customer", p["customer"])
        if p["action"].strip():
            db.add_action(cid, actor, "action", p["action"])
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not update the complaint: {exc}")
        raise


def render_actions_form(c: dict) -> None:
    cid = c["complaint_id"]
    staff = [""] + db.list_staff()
    with st.expander("Manage complaint", expanded=True):
        with st.form(f"manage_{cid}", clear_on_submit=True):
            a, b, d = st.columns(3)
            assignee = a.selectbox("Assign to", staff, index=staff.index(c["assigned_to"])
                                   if c["assigned_to"] in staff else 0,
                                   format_func=lambda x: x or "Unassigned")
            status = b.selectbox("Status", db.STATUSES, index=db.STATUSES.index(c["status"]))
            priority = d.selectbox("Priority", db.PRIORITIES, index=db.PRIORITIES.index(c["priority"]))
            internal = st.text_area("Internal comment (staff only)", height=80,
                                    placeholder="Visible to the helpdesk team only.")
            customer = st.text_area("Customer-facing remark", height=80,
                                    placeholder="Shown to the customer when they track this complaint.")
            action = st.text_area("Action taken", height=70,
                                  placeholder="e.g. Reshipped replacement, issued refund of ₹499.")
            saved = st.form_submit_button("Save changes", type="primary")

    if saved:
        pending = dict(assignee=assignee, status=status, priority=priority,
                       internal=internal, customer=customer, action=action)
        nothing = (assignee == (c["assigned_to"] or "") and status == c["status"]
                   and priority == c["priority"]
                   and not (internal.strip() or customer.strip() or action.strip()))
        if nothing:
            st.info("No changes to save.")
        elif status != c["status"] and status in CONFIRM_STATUSES:
            confirm_dialog(cid, pending)
        else:
            apply_changes(cid, pending)
            st.session_state["_toast"] = "Complaint updated"
            st.rerun()

    msg = st.session_state.pop("_toast", None)
    if msg:
        st.toast(msg, icon="✅")
