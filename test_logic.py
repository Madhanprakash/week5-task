"""Checks the search and the escalation rules. No API key needed.

Run with:  python test_logic.py
"""
from agents.kb_search import search
from agents.ticket_store import decide_escalation, valid_contact
from sample_complaints import ALL_SAMPLES, NEGATIVE, POSITIVE

passed = 0
failed = 0


def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


print("Positive samples: a document is found and the ticket is Resolved")
for s in POSITIVE:
    results = search(s["search_query"])
    sources = ", ".join(sorted({r["file"] for r in results}))
    check(f"{s['title']} finds a document ({sources or 'none'})", len(results) > 0)
    status, reason = decide_escalation(s["complaint"], s["urgency"], s["sentiment"],
                                       sources, s["confidence"])
    check(f"{s['title']} is Resolved", status == "Resolved")

print("\nNegative samples: the ticket is Escalated")
for s in NEGATIVE:
    if not s["search_query"]:
        continue  # the "too short" sample is rejected by the form, not by the rules
    results = search(s["search_query"])
    sources = ", ".join(sorted({r["file"] for r in results}))
    status, reason = decide_escalation(s["complaint"], s["urgency"], s["sentiment"],
                                       sources, s["confidence"])
    check(f"{s['title']} is Escalated ({reason})", status == "Escalated")

print("\nSingle rules")
base = dict(complaint="my order is late", urgency="Low", sentiment="Neutral",
            kb_sources="shipping_policy.md", confidence="High")
check("baseline is Resolved", decide_escalation(**base)[0] == "Resolved")
check("High urgency escalates", decide_escalation(**{**base, "urgency": "High"})[0] == "Escalated")
check("Very angry escalates", decide_escalation(**{**base, "sentiment": "Very angry"})[0] == "Escalated")
check("no document escalates", decide_escalation(**{**base, "kb_sources": "none"})[0] == "Escalated")
check("low confidence escalates", decide_escalation(**{**base, "confidence": "Low"})[0] == "Escalated")
check("lawyer escalates", decide_escalation(**{**base, "complaint": "I will call my lawyer"})[0] == "Escalated")
check("fraud escalates", decide_escalation(**{**base, "complaint": "this is fraud"})[0] == "Escalated")

print("\nContact field")
for good in ["priya@example.com", "9876543210", "+91 98765 43210", "(044) 2345-6789"]:
    check(f"accepts {good}", valid_contact(good))
for bad in ["", "abc", "12345", "priya@example", "priya @example.com", "1234567890123456", "---"]:
    check(f"rejects '{bad}'", not valid_contact(bad))

print("\nSamples fill every mandatory field")
for s in ALL_SAMPLES:
    check(s["title"], all(s[k].strip() for k in ["name", "order_id", "complaint"]) and valid_contact(s["contact"]))

print("\nReply mail")
import tempfile
from pathlib import Path

import agents.ticket_store as store

store.REPLY_MAILS_FILE = Path(tempfile.mkdtemp()) / "reply_mails.csv"
check("no reply mail yet", store.read_reply_mail("TKT-1") is None)
store.save_reply_mail("TKT-1", "helpdesk", "first")
store.save_reply_mail("TKT-1", "helpdesk", "second, with a comma\nand a new line")
store.save_reply_mail("TKT-2", "helpdesk", "other ticket")
check("latest save wins", store.read_reply_mail("TKT-1")["reply"] == "second, with a comma\nand a new line")

print("\nAsking for a person")
check("asking for a human escalates", decide_escalation(**{**base, "complaint": "let me talk to a real person"})[0] == "Escalated")
check("asking for a manager escalates", decide_escalation(**{**base, "complaint": "I want your manager"})[0] == "Escalated")

print("\nNew knowledge base topics")
for query, expected in [("cancel order", "orders_and_payments.md"), ("wrong item received", "orders_and_payments.md"),
                        ("payment failed money deducted", "orders_and_payments.md"), ("discount code", "orders_and_payments.md")]:
    check(f"'{query}' finds {expected}", any(r["file"] == expected for r in search(query)))

print("\nFirst reply clock")
from datetime import datetime

NOW = datetime(2026, 1, 2, 12, 0, 0)
ticket = {"ticket_id": "T1", "timestamp": "2026-01-02 11:30:00", "status": "Escalated", "urgency": "High"}
staff = {"timestamp": "2026-01-02 11:40:00", "helpdesk_user": "helpdesk"}
person = {"timestamp": "2026-01-02 11:50:00", "helpdesk_user": store.CUSTOMER_ACTOR}
check("due in 30m", store.reply_clock(ticket, [], None, NOW) == "Due in 30m")
check("overdue", store.reply_clock({**ticket, "timestamp": "2026-01-02 09:00:00"}, [], None, NOW) == "Overdue by 2h 0m")
check("staff action stops it", store.reply_clock(ticket, [staff], None, NOW) == "Replied")
check("reply mail stops it", store.reply_clock(ticket, [], staff, NOW) == "Replied")
check("customer asking again restarts it", store.reply_clock(ticket, [staff, person], None, NOW) == "Due in 50m")
check("resolved is not waiting", store.reply_clock({**ticket, "status": "Resolved"}, [], None, NOW) == "Not waiting")

print("\nTalking to a person, related tickets")
tmp = Path(tempfile.mkdtemp())
store.LOG_FILE, store.ACTIONS_FILE, store.CONTACTS_FILE = tmp / "t.csv", tmp / "a.csv", tmp / "c.csv"
for tid, order in [("T1", "ORD-1"), ("T2", "ord-1 "), ("T3", "ORD-3"), ("T4", "ORD-4"), ("T5", "Not given"), ("T6", "Not given")]:
    store.append_ticket({"ticket_id": tid, "timestamp": "2026-01-01 10:00:00", "order_id": order,
                         "status": "Resolved", "urgency": "Low"})
store.save_contact("T3", "A@example.com")
store.save_contact("T4", "a@example.com")
ids = lambda tid: [t["ticket_id"] for t in store.related_tickets(next(x for x in store.read_tickets() if x["ticket_id"] == tid))]
check("same order is related", ids("T1") == ["T2"])
check("same contact is related", ids("T3") == ["T4"])
check("'Not given' order is not a match", ids("T5") == [])
check("request_human escalates", store.request_human("T1"))
t1 = store.read_tickets()[0]
check("status and reason are saved", t1["status"] == "Escalated" and t1["escalation_reason"] == store.HUMAN_REQUEST_REASON)
check("other tickets are untouched", store.read_tickets()[1]["status"] == "Resolved")
check("unknown ticket fails", not store.request_human("NOPE"))

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
