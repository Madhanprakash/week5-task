"""Sample complaints for testing the support desk.

POSITIVE = the answer is in our knowledge base, so the ticket should be Resolved.
NEGATIVE = something should make the ticket Escalated (or be rejected).

Each sample has:
  name, order_id, contact, complaint  -> what you type into the form
  expected                   -> what the desk should do
  search_query               -> what the Knowledge Agent would search for
                                (used by test_logic.py, no API key needed)
"""

POSITIVE = [
    {
        "title": "1. Late delivery",
        "name": "Priya", "order_id": "ORD-4512", "contact": "priya@example.com",
        "complaint": "Where is my order? It was supposed to arrive yesterday.",
        "expected": "Shipping, answered from shipping_policy.md, Resolved",
        "search_query": "order arrive yesterday",
        "urgency": "Medium", "sentiment": "Neutral", "confidence": "High",
    },
    {
        "title": "2. Refund request",
        "name": "Arjun", "order_id": "ORD-7788", "contact": "9876500011",
        "complaint": "I want to return the shoes I bought last week. How do I get a refund?",
        "expected": "Refund, steps and 30-day window from refund_policy.md, Resolved",
        "search_query": "return refund shoes",
        "urgency": "Medium", "sentiment": "Neutral", "confidence": "High",
    },
    {
        "title": "3. Forgot password",
        "name": "Meera", "order_id": "ORD-2210", "contact": "meera@example.com",
        "complaint": "I forgot my password and can't log in.",
        "expected": "Account, reset steps from account_and_login.md, Resolved",
        "search_query": "forgot password login",
        "urgency": "Low", "sentiment": "Neutral", "confidence": "High",
    },
    {
        "title": "4. Broken blender",
        "name": "Karan", "order_id": "ORD-3021", "contact": "karan@example.com",
        "complaint": "The blender I received is broken. Can I get a replacement?",
        "expected": "Product / Refund, replacement process from refund_policy.md, Resolved",
        "search_query": "broken replacement",
        "urgency": "Medium", "sentiment": "Frustrated", "confidence": "High",
    },
]

NEGATIVE = [
    {
        "title": "5. Triple charge + lawyer",
        "name": "Rahul", "order_id": "ORD-9001", "contact": "+91 98765 00022",
        "complaint": "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer.",
        "expected": "Billing, High, Very angry, Escalated (urgency + payment/legal)",
        "search_query": "charged more than once",
        "urgency": "High", "sentiment": "Very angry", "confidence": "High",
    },
    {
        "title": "6. Not in our policies",
        "name": "Sara", "order_id": "ORD-5567", "contact": "sara@example.com",
        "complaint": "Do you sell gift cards for a company of 500 employees with custom branding?",
        "expected": "No matching document, honest 'I couldn't find this' reply, Escalated",
        "search_query": "gift cards custom branding",
        "urgency": "Low", "sentiment": "Neutral", "confidence": "Low",
    },
    {
        "title": "7. Furious customer",
        "name": "Vikram", "order_id": "ORD-1234", "contact": "vikram@example.com",
        "complaint": "This is the WORST service ever! My parcel is three weeks late and I am furious. Fix it NOW!",
        "expected": "Shipping, Very angry, Escalated (angry customer)",
        "search_query": "order late delivery",
        "urgency": "Medium", "sentiment": "Very angry", "confidence": "High",
    },
    {
        "title": "8. Fraud report",
        "name": "Neha", "order_id": "ORD-6620", "contact": "9876500033",
        "complaint": "Someone used my card on your site without asking me. This is fraud!",
        "expected": "Billing, Escalated (fraud keyword)",
        "search_query": "unauthorised card",
        "urgency": "High", "sentiment": "Frustrated", "confidence": "Medium",
    },
    {
        "title": "9. Off-topic question",
        "name": "Divya", "order_id": "ORD-8101", "contact": "divya@example.com",
        "complaint": "What is the weather in Chennai today?",
        "expected": "No matching document, Escalated",
        "search_query": "weather chennai today",
        "urgency": "Low", "sentiment": "Neutral", "confidence": "Low",
    },
    {
        "title": "10. Too short (rejected by the form)",
        "name": "Anil", "order_id": "ORD-8102", "contact": "anil@example.com",
        "complaint": "help",
        "expected": "The form shows a warning and no ticket is created",
        "search_query": "",
        "urgency": "Low", "sentiment": "Neutral", "confidence": "Low",
    },
]

ALL_SAMPLES = POSITIVE + NEGATIVE
