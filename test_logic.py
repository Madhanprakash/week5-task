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

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
