import hashlib
import json
import os
import re
import secrets
import time
from contextlib import closing
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from itsdangerous import BadData, URLSafeTimedSerializer
from pydantic import BaseModel, Field

from .beta import connect, identify

router = APIRouter(prefix="/auth/google")
FLOW_TTL = 600
TICKET_TTL = 60
SESSION_TTL = 8 * 60 * 60


def config():
    values = tuple(os.getenv(name, "") for name in (
        "MAILSCRIBE_GOOGLE_CLIENT_ID", "MAILSCRIBE_GOOGLE_CLIENT_SECRET",
        "MAILSCRIBE_GOOGLE_REDIRECT_URI", "MAILSCRIBE_CHROME_REDIRECT_URI",
        "MAILSCRIBE_AUTH_SECRET",
    ))
    if not all(values) or len(values[-1]) < 32 or not re.fullmatch(
        r"https://[a-p]{32}\.chromiumapp\.org/google", values[3]
    ):
        raise HTTPException(503, "Google sign-in is unavailable.")
    return values


def signer(secret, purpose):
    return URLSafeTimedSerializer(secret, salt=purpose)


def allowed_account(email):
    allowed = json.loads(os.getenv("MAILSCRIBE_GOOGLE_ACCOUNTS", "{}"))
    return allowed.get(email)


def redirect(url):
    return RedirectResponse(url, status_code=303, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    })


def ensure_ticket_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS google_login_tickets (
            digest TEXT PRIMARY KEY, challenge TEXT NOT NULL,
            email TEXT NOT NULL, subject TEXT NOT NULL, expires INTEGER NOT NULL
        )
    """)


@router.get("/start")
def start(challenge: str):
    if not re.fullmatch(r"[a-f0-9]{64}", challenge):
        raise HTTPException(400, "Invalid sign-in request.")
    client, _, callback, _, secret = config()
    nonce = secrets.token_urlsafe(32)
    state = signer(secret, "google-flow").dumps({"nonce": nonce, "challenge": challenge})
    query = urlencode({
        "client_id": client, "redirect_uri": callback, "response_type": "code",
        "scope": "openid email", "state": state, "nonce": nonce, "prompt": "select_account",
    })
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + query)


@router.get("/callback")
def callback(state: str = "", code: str = "", error: str = ""):
    client, client_secret, callback_url, chrome_url, secret = config()
    try:
        flow = signer(secret, "google-flow").loads(state, max_age=FLOW_TTL)
    except BadData as exc:
        raise HTTPException(400, "Sign-in expired. Try again.") from exc
    if error or not code:
        return redirect(chrome_url + "#error=cancelled")
    try:
        token_response = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": client, "client_secret": client_secret, "code": code,
            "grant_type": "authorization_code", "redirect_uri": callback_url,
        }, timeout=10)
        token_response.raise_for_status()
        claims = id_token.verify_oauth2_token(
            token_response.json()["id_token"], Request(), client
        )
    except (httpx.HTTPError, GoogleAuthError, KeyError, ValueError):
        return redirect(chrome_url + "#error=unavailable")
    if claims.get("nonce") != flow["nonce"]:
        return redirect(chrome_url + "#error=unavailable")

    email = claims.get("email", "").lower()
    if (claims.get("email_verified") is not True
            or not (email.endswith("@gmail.com") or claims.get("hd"))
            or not claims.get("sub") or not allowed_account(email)):
        return redirect(chrome_url + "#error=not_invited")

    ticket = secrets.token_urlsafe(32)
    hashed_ticket = hashlib.sha256(ticket.encode()).hexdigest()
    now = int(time.time())
    with closing(connect()) as db, db:
        ensure_ticket_table(db)
        db.execute("DELETE FROM google_login_tickets WHERE expires <= ?", (now,))
        db.execute("INSERT INTO google_login_tickets VALUES (?, ?, ?, ?, ?)",
                   (hashed_ticket, flow["challenge"], email, claims["sub"], now + TICKET_TTL))
    return redirect(chrome_url + "#ticket=" + ticket)


class TicketExchange(BaseModel):
    ticket: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    verifier: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/exchange")
def exchange(body: TicketExchange, response: Response):
    *_, secret = config()
    digest = hashlib.sha256(body.ticket.encode()).hexdigest()
    challenge = hashlib.sha256(body.verifier.encode()).hexdigest()
    with closing(connect()) as db, db:
        ensure_ticket_table(db)
        row = db.execute("""
            DELETE FROM google_login_tickets
            WHERE digest = ? AND challenge = ? AND expires > ?
            RETURNING email, subject
        """, (digest, challenge, int(time.time()))).fetchone()
        account = allowed_account(row[0]) if row else None
        if not account:
            raise HTTPException(401, "Sign-in expired. Try again.")
        db.execute("""
            CREATE TABLE IF NOT EXISTS google_account_links (
                account TEXT PRIMARY KEY, subject TEXT NOT NULL
            )
        """)
        db.execute("""
            INSERT INTO google_account_links (account, subject) VALUES (?, ?)
            ON CONFLICT(account) DO NOTHING
        """, (account, row[1]))
        subject = db.execute(
            "SELECT subject FROM google_account_links WHERE account = ?", (account,)
        ).fetchone()[0]
        if subject != row[1]:
            raise HTTPException(401, "This Google account cannot use this invitation.")
    response.headers["Cache-Control"] = "no-store"
    return {"token": signer(secret, "google-session").dumps(
        {"email": row[0], "account": account}
    )}


def identify_session(authorization):
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credential or len(credential) > 2048:
        raise HTTPException(401, "Sign in to MailScribe.")
    if re.fullmatch(r"[a-f0-9]{64}", credential):
        return identify(authorization)
    secret = os.getenv("MAILSCRIBE_AUTH_SECRET", "")
    if len(secret) >= 32:
        try:
            claims = signer(secret, "google-session").loads(credential, max_age=SESSION_TTL)
            account = allowed_account(claims["email"])
            if account and account == claims.get("account"):
                return account
        except BadData:
            pass
    raise HTTPException(401, "Sign in to MailScribe again.")
