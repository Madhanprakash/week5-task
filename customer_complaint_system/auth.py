"""Authentication: PBKDF2 password hashing, login/logout, helpdesk user seeding.

No password is stored in source. Initial accounts are created on first run from
environment variables (HELPDESK_ADMIN_PASSWORD / HELPDESK_AGENT_PASSWORD). If they
are not set, a random one-time password is generated and printed to the console.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time

import streamlit as st

import database as db

_ITERATIONS = 200_000
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def seed_users() -> None:
    """Create the initial helpdesk accounts if the users table is empty."""
    if db.count_users():
        return
    accounts = [
        ("admin", "admin@brightcart.example", "Asha Menon", "admin", "HELPDESK_ADMIN_PASSWORD"),
        ("agent", "agent@brightcart.example", "Ravi Kumar", "agent", "HELPDESK_AGENT_PASSWORD"),
        ("support", "support@brightcart.example", "Lena Fernandes", "agent", "HELPDESK_AGENT_PASSWORD"),
    ]
    for username, email, full, role, env in accounts:
        pw = os.getenv(env)
        generated = pw is None
        pw = pw or secrets.token_urlsafe(9)
        h, s = hash_password(pw)
        try:
            db.create_user(username, email, full, h, s, role)
        except sqlite3.IntegrityError:
            continue
        if generated:
            print(f"[auth] Created '{username}' with one-time password: {pw}  "
                  f"(set {env} in .env to choose your own)")


def login(identifier: str, password: str) -> tuple[bool, str]:
    """Validate credentials; throttles repeated failures. Returns (ok, message)."""
    locked_until = st.session_state.get("locked_until", 0)
    if time.time() < locked_until:
        return False, f"Too many attempts. Try again in {int(locked_until - time.time())}s."
    if not identifier.strip() or not password:
        return False, "Enter your username/email and password."
    user = db.get_user(identifier)
    if user and verify_password(password, user["password_hash"], user["salt"]):
        st.session_state.update(
            user={"username": user["username"], "name": user["full_name"], "role": user["role"]},
            failed_attempts=0)
        return True, "Welcome back!"
    fails = st.session_state.get("failed_attempts", 0) + 1
    st.session_state["failed_attempts"] = fails
    if fails >= MAX_ATTEMPTS:
        st.session_state["locked_until"] = time.time() + LOCKOUT_SECONDS
        st.session_state["failed_attempts"] = 0
    return False, "Incorrect username/email or password."


def logout() -> None:
    for k in ("user", "hd_selected", "hd_page"):
        st.session_state.pop(k, None)
    st.session_state["page"] = "home"


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_login() -> dict | None:
    return current_user()
