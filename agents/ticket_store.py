"""Reading and writing the ticket log, plus the escalation rules.

Kept free of AutoGen imports so the rules can be tested on their own.
"""
import csv
import re
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "tickets.csv"

HUMAN_REQUEST_REASON = "Customer asked for a person"

COLUMNS = [
    "ticket_id", "timestamp", "customer_name", "order_id", "complaint",
    "category", "urgency", "sentiment", "summary", "kb_sources",
    "response", "confidence", "status", "escalation_reason",
]

# Words that point to a legal threat, fraud or a payment dispute.
PAYMENT_LEGAL_PATTERN = re.compile(
    r"\b(lawyer|lawsuit|legal|attorney|sue|fraud|scam|chargeback|dispute|bank|charged)\b",
    re.IGNORECASE,
)
# Words that show the customer wants a person rather than the AI.
HUMAN_REQUEST_PATTERN = re.compile(
    r"\b(human|real person|a person|live agent|an agent|representative|manager|supervisor)\b",
    re.IGNORECASE,
)


def read_tickets() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def next_ticket_id() -> str:
    """TKT-0001, TKT-0002, ... based on the highest number already logged."""
    numbers = []
    for row in read_tickets():
        match = re.search(r"(\d+)$", row.get("ticket_id", ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"TKT-{(max(numbers) if numbers else 0) + 1:04d}"


def decide_escalation(complaint: str, urgency: str, sentiment: str,
                      kb_sources: str, confidence: str) -> tuple[str, str]:
    """Return (status, reason). Status is 'Escalated' if any rule fires."""
    reasons = []
    if urgency.strip().lower() == "high":
        reasons.append("High urgency")
    if "very angry" in sentiment.strip().lower():
        reasons.append("Very angry customer")
    if kb_sources.strip().lower() in ("", "none", "n/a"):
        reasons.append("No matching knowledge base document")
    if PAYMENT_LEGAL_PATTERN.search(complaint):
        reasons.append("Legal threat, fraud or payment dispute")
    if confidence.strip().lower() == "low":
        reasons.append("Low resolution confidence")
    if HUMAN_REQUEST_PATTERN.search(complaint):
        reasons.append(HUMAN_REQUEST_REASON)

    if reasons:
        return "Escalated", "; ".join(reasons)
    return "Resolved", ""


def append_ticket(row: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in COLUMNS})


def update_ticket_status(ticket_id: str, new_status: str) -> bool:
    """Overwrite the status field for one ticket. Returns True if found."""
    tickets = read_tickets()
    updated = False
    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = new_status
            updated = True
            break
    if not updated:
        return False
    with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(tickets)
    return True


# ---- Helpdesk actions -------------------------------------------------------
# Every action a helpdesk user takes is kept in its own small file, so the
# main tickets.csv keeps exactly the columns the assignment asks for.
ACTIONS_FILE = LOG_FILE.parent / "actions.csv"
ACTION_COLUMNS = ["ticket_id", "timestamp", "helpdesk_user", "new_status", "action_taken"]
VALID_STATUSES = ["Escalated", "Open", "In Progress", "Resolved", "Closed"]


def read_actions(ticket_id: str) -> list[dict]:
    """All actions for one ticket, newest first."""
    if not ACTIONS_FILE.exists():
        return []
    with ACTIONS_FILE.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["ticket_id"] == ticket_id]
    return rows[::-1]


def record_action(ticket_id: str, helpdesk_user: str, new_status: str, action_taken: str) -> bool:
    """Change the ticket status and save what was done. Returns False if it failed."""
    from datetime import datetime

    if new_status not in VALID_STATUSES:
        return False
    if not update_ticket_status(ticket_id, new_status):
        return False
    is_new = not ACTIONS_FILE.exists() or ACTIONS_FILE.stat().st_size == 0
    with ACTIONS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ACTION_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "ticket_id": ticket_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "helpdesk_user": helpdesk_user,
            "new_status": new_status,
            "action_taken": action_taken.strip(),
        })
    return True


# ---- Customer contact -------------------------------------------------------
# Kept in its own file for the same reason, and because tickets.csv already has
# rows with the old columns. Written by the app, so it never goes to the AI model.
CONTACTS_FILE = LOG_FILE.parent / "contacts.csv"
CONTACT_COLUMNS = ["ticket_id", "contact"]
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PHONE_PATTERN = re.compile(r"\+?[\d\s()-]+")


def valid_contact(value: str) -> bool:
    """True for a mail ID, or a phone number with 7 to 15 digits."""
    value = value.strip()
    if EMAIL_PATTERN.fullmatch(value):
        return True
    digits = sum(ch.isdigit() for ch in value)
    return bool(PHONE_PATTERN.fullmatch(value)) and 7 <= digits <= 15


def save_contact(ticket_id: str, contact: str) -> None:
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not CONTACTS_FILE.exists() or CONTACTS_FILE.stat().st_size == 0
    with CONTACTS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTACT_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({"ticket_id": ticket_id, "contact": contact.strip()})


def read_contact(ticket_id: str) -> str:
    """The saved contact for a ticket, or '' for older tickets without one."""
    if not CONTACTS_FILE.exists():
        return ""
    with CONTACTS_FILE.open(newline="", encoding="utf-8") as f:
        matches = [r["contact"] for r in csv.DictReader(f) if r["ticket_id"] == ticket_id]
    return matches[-1] if matches else ""


# ---- Reply mails ------------------------------------------------------------
# What the helpdesk wrote back to the requester. Every save is kept; the last one counts.
REPLY_MAILS_FILE = LOG_FILE.parent / "reply_mails.csv"
REPLY_MAIL_COLUMNS = ["ticket_id", "timestamp", "helpdesk_user", "reply"]


def save_reply_mail(ticket_id: str, helpdesk_user: str, reply: str) -> None:
    from datetime import datetime

    REPLY_MAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not REPLY_MAILS_FILE.exists() or REPLY_MAILS_FILE.stat().st_size == 0
    with REPLY_MAILS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPLY_MAIL_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "ticket_id": ticket_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "helpdesk_user": helpdesk_user,
            "reply": reply.strip(),
        })


def read_reply_mail(ticket_id: str) -> dict | None:
    """The latest saved reply mail for a ticket, or None."""
    if not REPLY_MAILS_FILE.exists():
        return None
    with REPLY_MAILS_FILE.open(newline="", encoding="utf-8") as f:
        matches = [r for r in csv.DictReader(f) if r["ticket_id"] == ticket_id]
    return matches[-1] if matches else None


# ---- Talking to a person, first reply targets, related tickets --------------
CUSTOMER_ACTOR = "customer"
WAITING_STATUSES = ["Escalated", "Open", "In Progress"]
# Business targets: change these to match what your team can really deliver.
FIRST_REPLY_HOURS = {"High": 1, "Medium": 8, "Low": 24}


def first_reply_hours(urgency: str) -> int:
    return FIRST_REPLY_HOURS.get(urgency.strip().title(), FIRST_REPLY_HOURS["Low"])


def request_human(ticket_id: str) -> bool:
    """The customer asked for a person: escalate the ticket and record why."""
    if not record_action(ticket_id, CUSTOMER_ACTOR, "Escalated", "Customer asked to talk to a person"):
        return False
    tickets = read_tickets()
    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id and HUMAN_REQUEST_REASON not in ticket["escalation_reason"]:
            ticket["escalation_reason"] = "; ".join(filter(None, [ticket["escalation_reason"], HUMAN_REQUEST_REASON]))
    with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(tickets)
    return True


def _duration(minutes: int) -> str:
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def reply_clock(ticket: dict, actions: list[dict], reply_mail: dict | None, now=None) -> str:
    """Where a ticket stands against its first reply target.

    The clock starts when the ticket is logged, or when the customer last asked
    for a person. Any later reply mail or staff action stops it.
    """
    from datetime import datetime, timedelta

    if ticket["status"] not in WAITING_STATUSES:
        return "Not waiting"
    start = max([ticket["timestamp"]] + [a["timestamp"] for a in actions
                                         if a["helpdesk_user"] == CUSTOMER_ACTOR])
    staff_times = [a["timestamp"] for a in actions if a["helpdesk_user"] != CUSTOMER_ACTOR]
    if reply_mail:
        staff_times.append(reply_mail["timestamp"])
    if any(when >= start for when in staff_times):
        return "Replied"

    due = (datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
           + timedelta(hours=first_reply_hours(ticket["urgency"])))
    minutes = int((due - (now or datetime.now())).total_seconds() // 60)
    return f"Due in {_duration(minutes)}" if minutes >= 0 else f"Overdue by {_duration(-minutes)}"


def related_tickets(ticket: dict) -> list[dict]:
    """Other tickets with the same order ID or contact, newest first. For staff only."""
    contacts = {}
    if CONTACTS_FILE.exists():
        with CONTACTS_FILE.open(newline="", encoding="utf-8") as f:
            contacts = {r["ticket_id"]: r["contact"].strip().lower() for r in csv.DictReader(f)}

    order_id = ticket["order_id"].strip().lower()
    contact = contacts.get(ticket["ticket_id"], "")
    matches = []
    for other in read_tickets():
        if other["ticket_id"] == ticket["ticket_id"]:
            continue
        same_order = order_id not in ("", "not given") and other["order_id"].strip().lower() == order_id
        same_contact = contact and contacts.get(other["ticket_id"]) == contact
        if same_order or same_contact:
            matches.append(other)
    return matches[::-1]
