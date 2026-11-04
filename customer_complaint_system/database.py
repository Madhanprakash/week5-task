"""SQLite data layer: schema, queries, complaint workflow and seed data."""
from __future__ import annotations

import hashlib
import random
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database" / "complaints.db"
UPLOAD_DIR = BASE_DIR / "uploads"

STATUSES = ["Open", "Assigned", "In Progress", "Pending Customer Response",
            "Resolved", "Closed", "Reopened"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
CATEGORIES = ["Delivery Delay", "Damaged / Wrong Item", "Refund & Payment",
              "Product Quality", "Account & Login", "Customer Service", "Other"]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".txt"}

_CRITICAL_WORDS = ("fraud", "scam", "unauthorized", "unauthorised", "hacked",
                   "stolen", "unsafe", "injur", "fire", "charged twice")
_HIGH_WORDS = ("refund", "damaged", "broken", "wrong item", "not received",
               "never arrived", "urgent")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'agent',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium',
    status TEXT NOT NULL DEFAULT 'Open',
    assigned_to TEXT,
    fingerprint TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id),
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id),
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,          -- created|status|assignment|priority|internal|customer|action
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_cid ON actions(complaint_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
"""


class DuplicateComplaint(Exception):
    def __init__(self, complaint_id: str):
        super().__init__(complaint_id)
        self.complaint_id = complaint_id


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)


# ---------------------------------------------------------------- users
def create_user(username: str, email: str, full_name: str, password_hash: str,
                salt: str, role: str = "agent") -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO users (username,email,full_name,password_hash,salt,role,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (username, email.lower(), full_name, password_hash, salt, role, now()))


def get_user(identifier: str) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM users WHERE username=? OR email=?",
                         (identifier.strip(), identifier.strip().lower())).fetchone()


def count_users() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_staff() -> list[str]:
    with connect() as c:
        return [r["full_name"] for r in
                c.execute("SELECT full_name FROM users ORDER BY full_name")]


# ------------------------------------------------------------ complaints
def suggest_priority(category: str, subject: str, description: str) -> str:
    text = f"{subject} {description}".lower()
    if any(w in text for w in _CRITICAL_WORDS):
        return "Critical"
    if category == "Refund & Payment" or any(w in text for w in _HIGH_WORDS):
        return "High"
    if category in ("Other", "Customer Service"):
        return "Low"
    return "Medium"


def _fingerprint(email: str, subject: str, description: str) -> str:
    norm = " ".join(f"{email}|{subject}|{description}".lower().split())
    return hashlib.sha256(norm.encode()).hexdigest()


def _new_complaint_id(conn: sqlite3.Connection) -> str:
    year = datetime.now().year
    while True:
        cid = f"CMP-{year}-{uuid.uuid4().hex[:6].upper()}"
        if not conn.execute("SELECT 1 FROM complaints WHERE complaint_id=?", (cid,)).fetchone():
            return cid


def safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:80] or "file"


def create_complaint(name: str, email: str, phone: str, category: str, subject: str,
                     description: str, attachment: tuple[str, bytes] | None = None,
                     created_at: str | None = None, priority: str | None = None,
                     status: str = "Open") -> str:
    """Insert a complaint. Raises DuplicateComplaint if an identical one exists."""
    email = email.strip().lower()
    fp = _fingerprint(email, subject, description)
    ts = created_at or now()
    with connect() as c:
        dup = c.execute("SELECT complaint_id FROM complaints WHERE fingerprint=?", (fp,)).fetchone()
        if dup:
            raise DuplicateComplaint(dup["complaint_id"])
        cid = _new_complaint_id(c)
        prio = priority or suggest_priority(category, subject, description)
        c.execute(
            "INSERT INTO complaints (complaint_id,customer_name,email,phone,category,subject,"
            "description,priority,status,fingerprint,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, name.strip(), email, phone.strip(), category, subject.strip(),
             description.strip(), prio, status, fp, ts, ts))
        c.execute("INSERT INTO actions (complaint_id,actor,kind,note,created_at)"
                  " VALUES (?,?,?,?,?)",
                  (cid, "Customer", "created", "Complaint submitted.", ts))
        if attachment:
            fname, data = attachment
            stored = UPLOAD_DIR / f"{cid}_{safe_filename(fname)}"
            stored.write_bytes(data)
            c.execute("INSERT INTO attachments (complaint_id,filename,stored_path,size_bytes,"
                      "uploaded_at) VALUES (?,?,?,?,?)",
                      (cid, safe_filename(fname), str(stored), len(data), ts))
    return cid


def get_complaint(cid: str) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM complaints WHERE complaint_id=?",
                         (cid.strip().upper(),)).fetchone()


def track_complaint(cid: str, email: str) -> dict | None:
    """Customer lookup: both ID and email must match. Hides internal notes."""
    row = get_complaint(cid)
    if not row or row["email"] != email.strip().lower():
        return None
    with connect() as c:
        history = c.execute(
            "SELECT actor,kind,note,created_at FROM actions WHERE complaint_id=?"
            " AND kind IN ('created','status','customer') ORDER BY id",
            (row["complaint_id"],)).fetchall()
    return {"complaint": dict(row), "history": [dict(h) for h in history]}


def all_complaints():
    import pandas as pd
    with connect() as c:
        return pd.read_sql_query("SELECT * FROM complaints ORDER BY created_at DESC", c)


def get_actions(cid: str) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM actions WHERE complaint_id=? ORDER BY id DESC", (cid,))]


def get_attachments(cid: str) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM attachments WHERE complaint_id=?", (cid,))]


def add_action(cid: str, actor: str, kind: str, note: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO actions (complaint_id,actor,kind,note,created_at)"
                  " VALUES (?,?,?,?,?)", (cid, actor, kind, note.strip(), now()))
        c.execute("UPDATE complaints SET updated_at=? WHERE complaint_id=?", (now(), cid))


def update_complaint(cid: str, actor: str, *, status: str | None = None,
                     assigned_to: str | None = None, priority: str | None = None) -> list[str]:
    """Apply changes and write an audit entry for each. Returns list of changes made."""
    changes: list[str] = []
    with connect() as c:
        row = c.execute("SELECT * FROM complaints WHERE complaint_id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("Complaint not found")
        ts = now()

        def log(kind: str, note: str) -> None:
            c.execute("INSERT INTO actions (complaint_id,actor,kind,note,created_at)"
                      " VALUES (?,?,?,?,?)", (cid, actor, kind, note, ts))
            changes.append(note)

        if status and status != row["status"]:
            if status not in STATUSES:
                raise ValueError("Invalid status")
            c.execute("UPDATE complaints SET status=? WHERE complaint_id=?", (status, cid))
            log("status", f"Status changed from {row['status']} to {status}.")
        if assigned_to is not None and assigned_to != (row["assigned_to"] or ""):
            c.execute("UPDATE complaints SET assigned_to=? WHERE complaint_id=?",
                      (assigned_to or None, cid))
            log("assignment", f"Assigned to {assigned_to}." if assigned_to else "Unassigned.")
            if assigned_to and row["status"] == "Open" and not status:
                c.execute("UPDATE complaints SET status='Assigned' WHERE complaint_id=?", (cid,))
                log("status", "Status changed from Open to Assigned.")
        if priority and priority != row["priority"]:
            if priority not in PRIORITIES:
                raise ValueError("Invalid priority")
            c.execute("UPDATE complaints SET priority=? WHERE complaint_id=?", (priority, cid))
            log("priority", f"Priority changed from {row['priority']} to {priority}.")
        if changes:
            c.execute("UPDATE complaints SET updated_at=? WHERE complaint_id=?", (ts, cid))
    return changes


# ------------------------------------------------------------------ seed
_SAMPLES = [
    ("Priya Sharma", "priya.sharma@example.com", "9876543210", "Delivery Delay",
     "Order 10 days late", "My order was due last week and tracking has not updated in 8 days."),
    ("Rahul Verma", "rahul.verma@example.com", "9123456780", "Refund & Payment",
     "Charged twice for one order", "I was charged twice for the same order and need a refund urgently."),
    ("Anita Desai", "anita.desai@example.com", "9988776655", "Damaged / Wrong Item",
     "Received a broken blender", "The blender jar arrived cracked. Packaging was damaged."),
    ("Mohan Iyer", "mohan.iyer@example.com", "9090909090", "Account & Login",
     "Cannot reset password", "The reset email never arrives and I am locked out of my account."),
    ("Sara Khan", "sara.khan@example.com", "9812345678", "Product Quality",
     "Headphones stopped working", "The left earbud died after two weeks of normal use."),
    ("Vikram Singh", "vikram.singh@example.com", "9700112233", "Customer Service",
     "Support did not reply", "I emailed support three times and nobody has replied."),
    ("Neha Gupta", "neha.gupta@example.com", "9654321098", "Refund & Payment",
     "Unauthorized transaction on my card", "There is an unauthorized charge from your store on my card."),
    ("Arjun Nair", "arjun.nair@example.com", "9555000111", "Delivery Delay",
     "Parcel marked delivered but not received", "Tracking says delivered yesterday but I never received it."),
    ("Meera Pillai", "meera.pillai@example.com", "9444333222", "Other",
     "Feedback on website search", "The site search returns irrelevant results most of the time."),
    ("Karan Mehta", "karan.mehta@example.com", "9333222111", "Product Quality",
     "Shoes size mismatch", "The shoes labelled size 9 fit like a size 7."),
]


def seed_sample_data() -> None:
    """Insert sample complaints once (only when the table is empty)."""
    with connect() as c:
        if c.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]:
            return
    rng = random.Random(7)
    staff = list_staff() or ["Unassigned"]
    for i in range(24):
        n, e, p, cat, subj, desc = _SAMPLES[i % len(_SAMPLES)]
        if i >= len(_SAMPLES):
            subj, desc = f"{subj} (#{i})", f"{desc} Reference batch {i}."
        ts = (datetime.now() - timedelta(days=rng.randint(0, 29),
                                         hours=rng.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        status = rng.choice(["Open", "Open", "Assigned", "In Progress", "In Progress",
                             "Pending Customer Response", "Resolved", "Resolved", "Closed", "Reopened"])
        try:
            cid = create_complaint(n, e, p, cat, subj, desc, created_at=ts, status=status)
        except DuplicateComplaint:
            continue
        if status != "Open":
            who = rng.choice(staff)
            with connect() as c:
                c.execute("UPDATE complaints SET assigned_to=? WHERE complaint_id=?", (who, cid))
                c.execute("INSERT INTO actions (complaint_id,actor,kind,note,created_at)"
                          " VALUES (?,?,?,?,?)", (cid, who, "status", f"Status set to {status}.", ts))
                c.execute("INSERT INTO actions (complaint_id,actor,kind,note,created_at)"
                          " VALUES (?,?,?,?,?)",
                          (cid, who, "internal", "Reviewed the case and contacted the logistics team.", ts))
