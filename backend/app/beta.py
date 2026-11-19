import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from fastapi import HTTPException


def identify(authorization: str | None) -> str:
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or len(credential) != 64:
        raise HTTPException(401, "Sign in to MailScribe with your invite key.")
    digest = hashlib.sha256(credential.encode()).hexdigest()
    invites = json.loads(os.getenv("MAILPOLISH_BETA_INVITES", "{}"))
    user = invites.get(digest)
    if not user:
        raise HTTPException(401, "This invite key is invalid or has been revoked.")
    return user


def connect():
    db = sqlite3.connect(os.getenv("MAILPOLISH_USAGE_DB", "mailpolish-usage.sqlite3"))
    db.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            account TEXT NOT NULL,
            day TEXT NOT NULL,
            requests INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (account, day)
        )
    """)
    return db


def reserve(user: str) -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    limit = int(os.getenv("MAILPOLISH_DAILY_LIMIT", "20"))
    if limit <= 0:
        raise HTTPException(429, "Daily rewrite limit reached. It resets at midnight UTC.")
    with closing(connect()) as db, db:
        cursor = db.execute("""
            INSERT INTO daily_usage (account, day, requests) VALUES (?, ?, 1)
            ON CONFLICT (account, day) DO UPDATE SET requests = requests + 1
            WHERE requests < ?
        """, (user, day, limit))
        if cursor.rowcount == 0:
            raise HTTPException(429, "Daily rewrite limit reached. It resets at midnight UTC.")
    return day


def record_tokens(user: str, day: str, input_tokens: int, output_tokens: int):
    with closing(connect()) as db, db:
        db.execute("""
            UPDATE daily_usage
            SET input_tokens = input_tokens + ?, output_tokens = output_tokens + ?
            WHERE account = ? AND day = ?
        """, (input_tokens, output_tokens, user, day))
