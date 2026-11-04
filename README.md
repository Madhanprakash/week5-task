# AI Customer Support Desk

A multi-agent customer support desk built with **AutoGen** (v0.4+), **Python** and **Streamlit**.
A complaint passes through four agents in order, and the result is logged to a file. Complicated cases are marked **Escalated** for human support.

```
Complaint → Query Agent → Knowledge Agent → Resolution Agent → Log Agent → tickets.csv
            (category,      (search_kb tool,    (reply using only    (log_ticket tool,
             urgency,        passages + file)    retrieved facts)     escalation rules)
             sentiment)
```

## Architecture

| Agent | File | Job | Tools |
|---|---|---|---|
| QueryAgent | `agents/query_agent.py` | Extracts category, urgency, sentiment, summary | none |
| KnowledgeAgent | `agents/knowledge_agent.py` | Searches `knowledge_base/` and cites file names | `search_kb` |
| ResolutionAgent | `agents/resolution_agent.py` | Writes the customer reply and a confidence level | none |
| LogAgent | `agents/log_agent.py` | Saves the ticket and applies escalation rules | `log_ticket` |

- `team.py` builds a `RoundRobinGroupChat` in the order Query → Knowledge → Resolution → Log. It stops when the Log Agent replies `LOGGED`, with a 12-message cap as a safety net.
- `agents/kb_search.py` holds the keyword search (no LLM needed for retrieval, so answers are grounded in the files).
- `agents/ticket_store.py` reads and writes `logs/tickets.csv` and contains the escalation rules.

### Escalation rules
The ticket is **Escalated** if any of these is true:
1. Urgency is `High`
2. Sentiment is `Very angry`
3. The Knowledge Agent found no matching document
4. The complaint mentions a legal threat, fraud or a payment dispute (keywords such as *lawyer, legal, fraud, chargeback, bank, charged*)
5. The Resolution Agent's confidence is `Low`

The rules run in Python inside `log_ticket`, not in the prompt, so the same ticket always gets the same status.

## Knowledge base
`knowledge_base/` contains four documents for the fictional store **BrightCart**:
- `shipping_policy.md` (delivery times, tracking, late orders, charges)
- `refund_policy.md` (30-day returns, refund timing, damaged items, billing errors)
- `account_and_login.md` (password reset, lockouts, 2FA)
- `product_faq.md` (warranty, appliance care, sizing, restocking)

Add a `## Heading` section to any file and the search picks it up automatically.

## Setup

Requires Python 3.10+.

```bash
git clone <your-repo-url> customer-support-agents
cd customer-support-agents

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env               # then put your real key in .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

`.env` is listed in `.gitignore`, so the key is never committed. If a key was ever pushed to GitHub, revoke it in your provider's dashboard and create a new one.

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501), fill in the four mandatory fields (name, order ID, phone or mail ID, complaint) and press **Submit complaint**.

- **Agent steps** appear live, one section per agent.
- **Customer reply** is shown in a highlighted box with a green *Resolved* or red *Escalated* badge.
- **Ticket Log** shows every row in `logs/tickets.csv` and lets you download it.

## Log file

Each complaint adds one row to `logs/tickets.csv` (created automatically):

`ticket_id, timestamp, customer_name, order_id, complaint, category, urgency, sentiment, summary, kb_sources, response, confidence, status, escalation_reason`

The customer's phone number or mail ID is saved separately in `logs/contacts.csv` (`ticket_id, contact`) and is not sent to the AI model.

## Test cases

| # | Complaint | Expected | Screenshot |
|---|---|---|---|
| 1 | "Where is my order? It was supposed to arrive yesterday." | Shipping · shipping_policy.md · Resolved | `screenshots/` |
| 2 | "I want to return the shoes I bought last week. How do I get a refund?" | Refund · refund_policy.md · Resolved | `screenshots/` |
| 3 | "I forgot my password and can't log in." | Account · account_and_login.md · Resolved | `screenshots/` |
| 4 | "The blender I received is broken. Can I get a replacement?" | Product/Refund · refund_policy.md · Resolved | `screenshots/` |
| 5 | "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer." | Billing · High · Very angry · Escalated | `screenshots/` |
| 6 | "Do you sell gift cards for a company of 500 employees with custom branding?" | No matching document · Escalated | `screenshots/` |
| 7 | *(your own test)* | | `screenshots/` |
| 8 | *(your own test)* | | `screenshots/` |

Retrieval (with the agent-style queries "order arrive yesterday", "return refund", "forgot password login", "broken replacement", "charged more than once") and the escalation rules were checked without an API key. Cases 1–6 still need to be run end to end and screenshotted.

## Project structure

```
customer-support-agents/
├── app.py                    # Streamlit UI
├── team.py                   # wires the agents into one AutoGen team
├── agents/
│   ├── query_agent.py        # Customer Query Agent
│   ├── knowledge_agent.py    # Knowledge Base Agent + search_kb tool
│   ├── resolution_agent.py   # Resolution Agent
│   ├── log_agent.py          # Log Agent + log_ticket tool
│   ├── kb_search.py          # keyword search over knowledge_base/
│   └── ticket_store.py       # CSV log + escalation rules
├── knowledge_base/           # company documents (.md)
├── logs/                     # tickets.csv is created here
├── screenshots/              # UI screenshots
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Notes and limitations
- Retrieval uses keyword matching. Embeddings with ChromaDB or FAISS are a possible upgrade.
- The model is set by `OPENAI_MODEL`. Other providers need a different AutoGen model client, and non-OpenAI model names may need a `model_info` entry.
- The escalation keyword list is short by design. "charged" is included, so a complaint that says a card was "charged" will be escalated; the word "charge" alone (e.g. "delivery charge") is not matched. Adjust `PAYMENT_LEGAL_PATTERN` in `agents/ticket_store.py` if that is too strict.
