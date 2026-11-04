# BrightCart Customer Complaint Management System

Streamlit + SQLite + Plotly. Customers submit and track complaints; the helpdesk team logs in to manage them.

## Install and run (Windows PowerShell)

```powershell
cd customer_complaint_system
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then edit .env and set your own passwords
streamlit run app.py
```

(macOS/Linux: `source .venv/bin/activate` and `cp .env.example .env`.)

Open http://localhost:8501.

## Helpdesk accounts

Created automatically on first run (when the database has no users), with passwords from `.env`:

| Username | Email | Password from |
|---|---|---|
| `admin` | admin@brightcart.example | `HELPDESK_ADMIN_PASSWORD` |
| `agent` | agent@brightcart.example | `HELPDESK_AGENT_PASSWORD` |
| `support` | support@brightcart.example | `HELPDESK_AGENT_PASSWORD` |

If you skip `.env`, random one-time passwords are printed in the terminal on first run.
Passwords are stored only as salted PBKDF2-SHA256 hashes. To reset accounts, delete `database/complaints.db`
(this also deletes all complaints) and restart.

## Try it

1. **Customer:** Home → *Submit a Complaint* → fill the form → note the Complaint ID → *Track Complaint* with ID + email.
2. **Helpdesk:** top-right *Login* → Dashboard (KPIs, charts) → *Complaints* → filter, click a row, assign, comment,
   change status. Resolved/Closed/Reopened ask for confirmation. Customer-facing remarks show on the tracking page;
   internal comments do not.
3. 24 sample complaints (e.g. priya.sharma@example.com) are seeded on first run, so the dashboard has data.

## Structure

```
app.py          router, top bar, login page, bootstrap
database.py     SQLite schema, queries, workflow rules, seed data
auth.py         password hashing, login/logout, lockout, user seeding
customer.py     home, complaint form + validation, tracking
helpdesk.py     sidebar, filters, table, detail view, actions
dashboard.py    KPI cards and Plotly charts
styles.css      theme and responsive rules
database/       complaints.db (created on first run)
uploads/        customer attachments
```

## Notes

- Duplicate submissions (same email + subject + description) are rejected and the existing ID is shown.
- Priority is auto-suggested from keywords/category and can be changed by helpdesk staff.
- Uploads: PNG/JPG/PDF/TXT up to 5 MB; filenames are sanitised.
- 5 failed logins lock that browser session for 60 seconds.
