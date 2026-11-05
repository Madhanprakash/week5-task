"""Streamlit UI for the AI Customer Support Desk.

Run with:  streamlit run app.py

Pages (kept in st.session_state["page"]):
  customer  - complaint form + summary report (all that customers see)
  login     - helpdesk sign in
  helpdesk  - all tickets, ticket details, reply mail, actions and status updates
"""
import asyncio
import hmac
import html
import os
from urllib.parse import quote

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agents.ticket_store import (LOG_FILE, VALID_STATUSES, WAITING_STATUSES,
                                 first_reply_hours, read_actions, read_contact,
                                 read_reply_mail, read_tickets, record_action,
                                 related_tickets, reply_clock, request_human,
                                 save_contact, save_reply_mail, valid_contact)
from sample_complaints import ALL_SAMPLES
from team import run_ticket

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Helpdesk login. Set HELPDESK_USER and HELPDESK_PASS in your .env file.
# The defaults below are for local demos only.
HELPDESK_USER = os.getenv("HELPDESK_USER", "helpdesk")
HELPDESK_PASS = os.getenv("HELPDESK_PASS", "support123")
USING_DEFAULT_LOGIN = "HELPDESK_PASS" not in os.environ

RULES = [
    "Urgency is High",
    "Customer is very angry",
    "No matching company document",
    "Legal threat, fraud or payment dispute",
    "Reply confidence is Low",
    "Customer asks for a person",
]
# The first thing an experienced colleague would check, by ticket category.
FIRST_STEPS = {
    "Shipping": "Check the carrier tracking for this order and open a trace if it is late.",
    "Refund": "Check whether the return was scanned at the warehouse and where the refund has got to.",
    "Billing": "Check the payment records for this order and confirm what was actually charged.",
    "Account": "Confirm the customer's identity before changing anything on the account.",
    "Product": "Check the customer's photos, then offer a replacement or a refund.",
}
FORM_KEYS = ["name", "order", "contact", "complaint"]
STATUS_COLOURS = {
    "Escalated": "background-color:#FFEBE9;color:#82071E;font-weight:600",
    "Resolved": "background-color:#DAFBE1;color:#116329;font-weight:600",
    "Open": "background-color:#dbeafe;color:#1e40af;font-weight:600",
    "In Progress": "background-color:#fef9c3;color:#854d0e;font-weight:600",
    "Closed": "background-color:#e5e7eb;color:#374151;font-weight:600",
}

st.set_page_config(page_title="BrightCart Support", page_icon="🛒", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #F6F7F9; border-right: 1px solid #E3E6EA; }
[data-testid="stSidebar"][aria-expanded="true"] { width: 260px !important; min-width: 260px !important; }
[data-testid="stMainBlockContainer"] { padding: 48px 40px 32px; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #57606A !important; opacity: 1 !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] ul { padding-left: 18px; margin: 0; }
[data-testid="stSidebar"] li { font-size: 14px; line-height: 1.7; margin: 0; padding: 0; }
h1 { font-size: 34px !important; font-weight: 700 !important; padding: 0 !important; }

/* Inputs: white with a thin border */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
    background: #fff !important; border-color: #D0D7DE !important; border-radius: 6px !important;
}
[data-testid="stMain"] input, [data-testid="stMain"] textarea, [data-testid="stMain"] [data-baseweb="select"] div { background: #fff !important; }

/* Summary cards, and the borderless version under a ticket result */
[data-testid="stMetric"] { border: 1px solid #E3E6EA; border-radius: 8px; padding: 14px 16px; }
[data-testid="stMetricLabel"] p { font-size: 13px; color: #57606A; }
[data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; }
[class*="st-key-result_stats"] [data-testid="stMetric"] { border: 0; padding: 0; }
[class*="st-key-result_stats"] [data-testid="stMetricValue"] { font-size: 20px; font-weight: 600; }

.bc-brand { font-weight: 700; font-size: 18px; }
.bc-label { font-size: 13px; color: #57606A; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.bc-heading { font-size: 20px; font-weight: 700; }
.bc-banner { border-radius: 6px; padding: 12px 16px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.bc-banner b { font-weight: 700; }
.bc-banner small { display: block; margin-top: 6px; font-size: 13px; color: #57606A; }
.bc-ok { background: #DAFBE1; color: #116329; font-weight: 600; }
.bc-bad { background: #FFEBE9; color: #82071E; border-left: 4px solid #CF222E; }
.bc-reply { background: #DDF4FF; color: #0A3069; }
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state["page"] = "customer"


# ------------------------------------------------------------------ helpers
def go(page):
    st.session_state["page"] = page
    st.rerun()


def find_ticket(ticket_id):
    for row in read_tickets():
        if row["ticket_id"] == ticket_id:
            return row
    return None


def colour_status(value):
    return STATUS_COLOURS.get(value, "")


def load_sample(sample):
    """Button callback: put the chosen sample into the form fields."""
    st.session_state["name"] = sample["name"]
    st.session_state["order"] = sample["order_id"]
    st.session_state["contact"] = sample["contact"]
    st.session_state["complaint"] = sample["complaint"]


def banner(kind, title="", body="", note=""):
    """Coloured box (ok, bad or reply). All text is escaped: it can come from customers."""
    parts = []
    if title:
        parts.append(f"<b>{html.escape(title)}</b>")
    if body:
        parts.append(html.escape(body))
    inner = "\n".join(parts)
    if note:
        inner += f"<small>{html.escape(note)}</small>"
    st.html(f"<div class='bc-banner bc-{kind}'>{inner}</div>")


def top_bar():
    """Title on the left, ONE button on the right (Login or Logout)."""
    left, right = st.columns([6, 1], vertical_alignment="center")
    left.title("AI Customer Support Desk", anchor=False)
    left.caption("Complaints are answered by our AI support assistant, using BrightCart's own policies.")
    page = st.session_state["page"]
    if st.session_state.get("user"):
        if right.button("Logout", width="stretch"):
            st.session_state.pop("user")
            go("customer")
    elif page == "login":
        if right.button("← Back", width="stretch"):
            go("customer")
    else:
        if right.button("Login", type="primary", width="stretch"):
            go("login")


def sidebar():
    """Customers see one line about the assistant. Staff also see the rules and API status."""
    with st.sidebar:
        st.html("<div class='bc-brand'>🛒 BrightCart Support</div>")
        user = st.session_state.get("user")
        if not user:
            st.caption("Our AI support assistant reads your complaint and replies using BrightCart's policies.")
            return
        st.caption(f"Signed in as **{user}**")
        st.html("<div class='bc-label'>Escalated when any is true</div>")
        st.markdown("\n".join(f"- {rule}" for rule in RULES))
        if os.getenv("OPENAI_API_KEY"):
            banner("ok", body=f"API key loaded · model {MODEL}")
        else:
            banner("bad", body="OPENAI_API_KEY is not set.")


def customer_summary(ticket):
    """The summary report: the only ticket information a customer sees."""
    st.html(f"<div class='bc-heading'>Summary report for {html.escape(ticket['ticket_id'])}</div>")
    if ticket["status"] in ("Resolved", "Closed"):
        banner("ok", body=f"🟢 {ticket['status']}")
    elif ticket["status"] == "Escalated":
        banner("reply", body="Our support team is looking at your complaint and will follow up with you.",
               note=f"We aim to reply within {first_reply_hours(ticket['urgency'])} hours.")
    else:
        banner("reply", body=f"Status: {ticket['status']}")
    st.markdown("**Your complaint in brief**")
    st.write(ticket["summary"])
    st.markdown("**Our reply**")
    saved = read_reply_mail(ticket["ticket_id"])
    banner("reply", body=saved["reply"] if saved else ticket["response"])
    if ticket["status"] == "Resolved" and st.button("This didn't solve it, talk to a person"):
        request_human(ticket["ticket_id"])
        st.rerun()


def handoff_brief(ticket):
    """Everything a person needs to take over, so the customer never has to repeat themselves."""
    st.markdown("### Handoff brief")
    actions = read_actions(ticket["ticket_id"])
    st.markdown(f"**First reply:** {reply_clock(ticket, actions, read_reply_mail(ticket['ticket_id']))}")
    st.markdown(f"**What they need:** {ticket['summary']}")
    first_step = FIRST_STEPS.get(ticket["category"], "Read the complaint and decide who should own it.")
    st.markdown(f"**Suggested first step:** {first_step}")
    if "very angry" in ticket["sentiment"].lower():
        st.markdown("**Tone:** Acknowledge their frustration first. Call them if they gave a phone number.")
    if "legal" in ticket["escalation_reason"].lower():
        st.markdown("**Care:** Possible legal threat, fraud or payment dispute. "
                    "Ask a senior specialist before promising anything.")

    others = related_tickets(ticket)
    if others:
        st.markdown(f"**Same order or contact:** {len(others)} other ticket(s). Read these before replying.")
        st.dataframe(pd.DataFrame(others)[["ticket_id", "timestamp", "status", "summary"]],
                     hide_index=True, width="stretch")
    else:
        st.markdown("**Same order or contact:** No other tickets.")


def show_result(ticket):
    """The full ticket, for helpdesk staff."""
    st.html(f"<div class='bc-heading'>Result for {html.escape(ticket['ticket_id'])}</div>")
    reason = ticket["escalation_reason"]
    if ticket["status"] == "Escalated":
        banner("bad", "🔴 Escalated to human support", f"Reason: {reason}")
    elif ticket["status"] == "Resolved":
        banner("ok", body="🟢 Resolved" if reason else "🟢 Resolved by the AI desk")
    else:
        banner("reply", body=f"Status: {ticket['status']}")

    with st.container(key="result_stats"):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Category", ticket["category"])
        m2.metric("Urgency", ticket["urgency"])
        m3.metric("Sentiment", ticket["sentiment"])
        m4.metric("Reply confidence", ticket["confidence"])

    if ticket["status"] in WAITING_STATUSES:
        handoff_brief(ticket)

    with st.expander("More details", expanded=True):
        st.markdown(f"**Ticket ID:** {ticket['ticket_id']} · **Logged at:** {ticket['timestamp']}")
        st.markdown(f"**Customer:** {ticket['customer_name'] or 'Not given'} · "
                    f"**Order ID:** {ticket['order_id'] or 'Not given'}")
        st.markdown(f"**Phone or mail ID:** {read_contact(ticket['ticket_id']) or 'Not given'}")
        st.markdown(f"**Knowledge source:** {ticket['kb_sources'] or 'none'}")
        st.markdown(f"**Summary:** {ticket['summary']}")
        st.markdown(f"**Original complaint:** {ticket['complaint']}")


def reply_mail_section(ticket):
    """Reply to the requester, filled in automatically from the AI reply. Staff can edit it."""
    ticket_id = ticket["ticket_id"]
    contact = read_contact(ticket_id)
    saved = read_reply_mail(ticket_id)

    st.markdown("### Reply mail to the requester")
    st.caption(f"To: {contact or 'No phone or mail ID saved for this ticket'}")
    reply = st.text_area("Mail content", value=saved["reply"] if saved else ticket["response"],
                         key=f"reply_mail_{ticket_id}", height=220)
    if st.button("Save reply mail", type="primary"):
        if reply.strip():
            save_reply_mail(ticket_id, st.session_state["user"], reply)
            st.toast(f"Reply mail saved for {ticket_id}", icon="✅")
            st.rerun()
        else:
            st.warning("The mail content is empty.")

    if not saved:
        st.caption("Not saved yet. This is the AI's reply.")
        return
    st.caption(f"Last saved by {saved['helpdesk_user']} at {saved['timestamp']}.")
    if "@" in contact:
        subject = f"BrightCart Support: your ticket {ticket_id}"
        url = f"mailto:{quote(contact, safe='@')}?subject={quote(subject)}&body={quote(saved['reply'])}"
        st.link_button("Open saved mail in mail app", url)
    elif contact:
        st.caption(f"The customer gave a phone number. Call or text {contact} with this reply.")


def submit_complaint(customer_name, order_id, contact, complaint):
    """Check the four mandatory fields, then run the AI. Reruns the page on success."""
    problems = []
    if not customer_name.strip():
        problems.append("Please enter your name.")
    if not order_id.strip():
        problems.append("Please enter your order ID.")
    if not contact.strip():
        problems.append("Please enter your phone number or mail ID.")
    elif not valid_contact(contact):
        problems.append("Please enter a valid phone number or mail ID.")
    if len(complaint.strip()) < 10:
        problems.append("Please describe the problem in at least 10 characters.")
    if problems:
        for problem in problems:
            st.error(problem)
        return
    if not os.getenv("OPENAI_API_KEY"):
        st.error("The support desk is not set up yet (OPENAI_API_KEY is missing).")
        return

    with st.spinner("Our AI assistant is reviewing your complaint..."):
        try:
            # The contact is not part of the task, so it never reaches the AI model.
            result = asyncio.run(run_ticket(customer_name, order_id, complaint))
        except Exception as error:
            st.error(f"Sorry, we could not process your complaint: {error}")
            return

    save_contact(result["ticket_id"], contact)
    st.session_state["confirmation_id"] = result["ticket_id"]
    st.session_state["clear_form"] = True  # an empty form can't be submitted twice by accident
    st.rerun()


# ================================================================== PAGE 1: customer
def complaint_section():
    """The form, with the summary report under it. Also the helpdesk's New complaint tab."""
    if st.session_state.pop("clear_form", False):
        for key in FORM_KEYS:
            st.session_state[key] = ""  # removing the key would leave the old text on screen

    # Demo helper: fill the form with a sample complaint.
    titles = [s["title"] for s in ALL_SAMPLES]
    pick, button = st.columns([3, 1], vertical_alignment="bottom")
    choice = pick.selectbox("Try a sample complaint", titles)
    sample = ALL_SAMPLES[titles.index(choice)]
    button.button("Load sample", on_click=load_sample, args=(sample,), width="stretch")

    col1, col2, col3 = st.columns(3)
    customer_name = col1.text_input("Your name (mandatory)", key="name", placeholder="e.g. Priya")
    order_id = col2.text_input("Order ID (mandatory)", key="order", placeholder="e.g. ORD-4512")
    contact = col3.text_input("Phone no or mail ID (mandatory)", key="contact",
                              placeholder="e.g. 9876543210 or priya@example.com")
    complaint = st.text_area("Describe your complaint (mandatory)", key="complaint", height=92,
                             placeholder="What happened? Include dates and order details.")
    st.caption(f"{len(complaint)} characters")

    if st.button("Submit complaint", type="primary"):
        submit_complaint(customer_name, order_id, contact, complaint)

    done_id = st.session_state.get("confirmation_id")
    if done_id:
        st.divider()
        ticket = find_ticket(done_id)
        if ticket:
            customer_summary(ticket)
        else:
            banner("ok", body=f"Complaint received. Your ticket number is {done_id}.")


def customer_page():
    complaint_section()


# ================================================================== PAGE 2: login
def login_page():
    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        st.subheader("🔐 Helpdesk Login")
        st.caption("For BrightCart helpdesk team members only.")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            ok = st.form_submit_button("Sign in", type="primary", width="stretch")
        if USING_DEFAULT_LOGIN:
            st.info("Demo login: **helpdesk** / **support123**.")
        if ok:
            user_ok = hmac.compare_digest(username.encode(), HELPDESK_USER.encode())
            pass_ok = hmac.compare_digest(password.encode(), HELPDESK_PASS.encode())
            if user_ok and pass_ok:
                st.session_state["user"] = username
                go("helpdesk")
            else:
                st.error("Incorrect username or password.")


# ================================================================== PAGE 3: helpdesk
def helpdesk_page():
    tickets = read_tickets()
    total = len(tickets)
    # A ticket keeps its escalation reason even after staff change its status.
    escalated = sum(1 for t in tickets if t["escalation_reason"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tickets logged", total)
    m2.metric("Resolved by AI", total - escalated)
    m3.metric("Escalated to humans", escalated)
    m4.metric("Escalation rate", f"{round(100 * escalated / total) if total else 0}%")

    new_label, log_label, insights_label = "✍️ New complaint", "📋 Ticket log", "📊 Insights"
    tab_new, tab_log, tab_insights = st.tabs([new_label, log_label, insights_label], default=log_label)
    with tab_new:
        complaint_section()
    with tab_log:
        ticket_log_tab(tickets)
    with tab_insights:
        insights_tab(tickets)


def ticket_log_tab(tickets):
    if not tickets:
        st.info("No complaints yet. They appear here as customers submit them.")
        return

    df = pd.DataFrame(tickets)
    f1, f2, f3 = st.columns([1, 2, 2])
    # Opens on escalated tickets, so the newest one is chosen automatically below.
    status_filter = f1.selectbox("Status", ["All"] + VALID_STATUSES, index=VALID_STATUSES.index("Escalated") + 1)
    category_filter = f2.multiselect("Category", sorted(df["category"].dropna().unique()),
                                     placeholder="Select categories")
    search = f3.text_input("Search name, order, complaint or reply", placeholder="e.g. refund")

    shown = df
    if status_filter != "All":
        shown = shown[shown["status"] == status_filter]
    if category_filter:
        shown = shown[shown["category"].isin(category_filter)]
    if search.strip():
        text = search.strip()
        mask = pd.Series(False, index=shown.index)
        for column in ["customer_name", "order_id", "complaint", "response"]:
            mask = mask | shown[column].str.contains(text, case=False, na=False, regex=False)
        shown = shown[mask]

    clocks = [reply_clock(row, read_actions(row["ticket_id"]), read_reply_mail(row["ticket_id"]))
              for row in shown.to_dict("records")]
    overdue = sum(clock.startswith("Overdue") for clock in clocks)
    st.caption(f"Showing {len(shown)} of {len(df)} tickets · {overdue} overdue for a first reply")
    columns = ["ticket_id", "timestamp", "customer_name", "order_id", "category", "urgency",
               "status", "first_reply", "escalation_reason", "summary"]
    grid = shown.assign(first_reply=clocks).iloc[::-1][columns]
    st.dataframe(grid.style.map(colour_status, subset=["status"]), hide_index=True, width="stretch")

    d1, d2, _ = st.columns(3)
    d1.download_button("Download filtered view (CSV)", shown.to_csv(index=False),
                       file_name="tickets_filtered.csv", mime="text/csv",
                       disabled=shown.empty, width="stretch")
    d2.download_button("Download full log (CSV)", LOG_FILE.read_bytes(),
                       file_name="tickets.csv", mime="text/csv", width="stretch")

    if shown.empty:
        return
    st.divider()
    ticket_id = st.selectbox("Open a complaint", shown["ticket_id"].tolist()[::-1])
    ticket_details(find_ticket(ticket_id))


def ticket_details(ticket):
    show_result(ticket)
    reply_mail_section(ticket)

    # ---- take action + update status
    st.markdown("### Take action")
    with st.form(f"action_form_{ticket['ticket_id']}", clear_on_submit=True):
        new_status = st.selectbox("Update status", VALID_STATUSES,
                                  index=VALID_STATUSES.index(ticket["status"])
                                  if ticket["status"] in VALID_STATUSES else 0)
        action_taken = st.text_area("Action taken", placeholder="e.g. Called the customer and arranged a replacement.")
        save = st.form_submit_button("Save action", type="primary")
    if save:
        if not action_taken.strip() and new_status == ticket["status"]:
            st.warning("Write the action you took or choose a new status.")
        elif record_action(ticket["ticket_id"], st.session_state["user"], new_status, action_taken):
            st.toast(f"{ticket['ticket_id']} saved as {new_status}", icon="✅")
            st.rerun()
        else:
            st.error("Could not save the action. Please try again.")

    history = read_actions(ticket["ticket_id"])
    st.markdown("**Action history**")
    if history:
        st.dataframe(pd.DataFrame(history).rename(columns={
            "timestamp": "When", "helpdesk_user": "By", "new_status": "Status", "action_taken": "Action"
        })[["When", "By", "Status", "Action"]], hide_index=True, width="stretch")
    else:
        st.caption("No actions recorded yet.")


def insights_tab(tickets):
    if not tickets:
        st.info("Charts appear after the first ticket is logged.")
        return
    df = pd.DataFrame(tickets)
    left, right = st.columns(2)
    with left:
        st.markdown("**Tickets by category**")
        st.bar_chart(df["category"].value_counts())
    with right:
        st.markdown("**Tickets by status**")
        st.bar_chart(df["status"].value_counts())
    left, right = st.columns(2)
    with left:
        st.markdown("**Tickets by urgency**")
        st.bar_chart(df["urgency"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0))
    with right:
        st.markdown("**Why tickets were escalated**")
        reasons = (df["escalation_reason"].dropna().str.split("; ").explode()
                   .loc[lambda s: s != ""].value_counts())
        if reasons.empty:
            st.caption("No escalations yet.")
        else:
            st.bar_chart(reasons)


# ================================================================== router
page = st.session_state["page"]

# The helpdesk page is only available after logging in.
if page == "helpdesk" and not st.session_state.get("user"):
    page = st.session_state["page"] = "login"

sidebar()
top_bar()

if page == "login":
    login_page()
elif page == "helpdesk":
    helpdesk_page()
else:
    customer_page()
