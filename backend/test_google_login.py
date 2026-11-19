import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient

from app.main import app

with tempfile.TemporaryDirectory() as temp:
    redirect_uri = "https://" + "a" * 32 + ".chromiumapp.org/google"
    verifier = secrets.token_hex(32)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    invite = secrets.token_hex(32)
    env = {
        "MAILPOLISH_USAGE_DB": str(Path(temp) / "usage.sqlite3"),
        "MAILPOLISH_BETA_INVITES": json.dumps({
            hashlib.sha256(invite.encode()).hexdigest(): "owner",
        }),
        "MAILSCRIBE_GOOGLE_CLIENT_ID": "example-client",
        "MAILSCRIBE_GOOGLE_CLIENT_SECRET": "test-only",
        "MAILSCRIBE_GOOGLE_REDIRECT_URI": "https://example.org/auth/google/callback",
        "MAILSCRIBE_CHROME_REDIRECT_URI": redirect_uri,
        "MAILSCRIBE_AUTH_SECRET": secrets.token_hex(32),
        "MAILSCRIBE_GOOGLE_ACCOUNTS": '{"tester@gmail.com":"owner"}',
    }
    with patch.dict(os.environ, env), TestClient(app, follow_redirects=False) as client:
        assert client.get("/auth/google/start?challenge=bad").status_code == 400
        start = client.get("/auth/google/start", params={"challenge": challenge})
        assert start.status_code == 303
        assert start.headers["location"].startswith("https://accounts.google.com/")
        query = parse_qs(urlsplit(start.headers["location"]).query)
        state, nonce = query["state"][0], query["nonce"][0]
        assert query["scope"] == ["openid email"]
        assert client.get("/auth/google/callback?state=invalid&code=x").status_code == 400

        def callback(email, sub="google-user", verified=True, token_nonce=nonce):
            with patch("app.google_login.httpx.post", return_value=httpx.Response(
                200, json={"id_token": "fixture"},
                request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
            )), patch("app.google_login.id_token.verify_oauth2_token", return_value={
                "email": email, "email_verified": verified, "sub": sub, "nonce": token_nonce,
            }):
                return client.get("/auth/google/callback", params={"state": state, "code": "fixture"})

        assert callback("stranger@gmail.com").headers["location"] == redirect_uri + "#error=not_invited"
        assert callback("tester@gmail.com", verified=False).headers["location"].endswith("#error=not_invited")
        assert callback("tester@gmail.com", token_nonce="bad").headers["location"].endswith("#error=unavailable")

        def get_ticket(response):
            assert response.status_code == 303
            return parse_qs(urlsplit(response.headers["location"]).fragment)["ticket"][0]

        def exchange(ticket, proof=verifier):
            return client.post("/auth/google/exchange", json={"ticket": ticket, "verifier": proof})

        ticket = get_ticket(callback("tester@gmail.com"))
        assert exchange(ticket, secrets.token_hex(32)).status_code == 401
        session = exchange(ticket)
        assert session.status_code == 200
        assert exchange(ticket).status_code == 401
        headers = {"Authorization": "Bearer " + session.json()["token"]}
        assert client.get("/session", headers=headers).status_code == 200
        assert client.get("/session", headers={"Authorization": "Bearer " + invite}).status_code == 200
        assert exchange(get_ticket(callback("tester@gmail.com", sub="other-user"))).status_code == 401
        os.environ["MAILSCRIBE_GOOGLE_ACCOUNTS"] = "{}"
        assert client.get("/session", headers=headers).status_code == 401

print("Passed Google sign-in fixture, allowlist, proof binding, one-time exchange, subject binding, revocation and legacy sign-in.")
