"""Reading and writing the ticket log, plus the escalation rules.

Kept free of AutoGen imports so the rules can be tested on their own.
"""
import csv
import re
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "tickets.csv"

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
