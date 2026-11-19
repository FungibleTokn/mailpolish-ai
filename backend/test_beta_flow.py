import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.main import app

with tempfile.TemporaryDirectory() as temp:
    db = Path(temp) / "usage.sqlite3"
    keys = {name: secrets.token_hex(32) for name in ("tester-a", "tester-b")}
    env = {
        "OPENAI_API_KEY": "test-only",
        "MAILPOLISH_DAILY_LIMIT": "2",
        "MAILPOLISH_USAGE_DB": str(db),
        "MAILPOLISH_BETA_INVITES": json.dumps({
            hashlib.sha256(key.encode()).hexdigest(): name for name, key in keys.items()
        }),
    }
    model = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Could you send the report?"))],
        usage=SimpleNamespace(prompt_tokens=90, completion_tokens=10),
    ))
    body = {"text": "send the report please", "mode": "professional"}

    with patch.dict(os.environ, env), patch("app.main.AsyncOpenAI") as provider:
        provider.return_value.chat.completions.create = model
        with TestClient(app) as client:
            headers = {name: {"Authorization": f"Bearer {key}"} for name, key in keys.items()}
            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/session").status_code == 401
            assert client.get("/session", headers={"Authorization": "Bearer " + "0" * 64}).status_code == 401
            assert client.post("/rewrite", json=body, headers={"X-Dev-Token": "test-only"}).status_code == 401
            for account in headers.values():
                assert client.get("/session", headers=account).json() == {"signed_in": True}

            def rewrite(account):
                return client.post("/rewrite", json=body, headers=headers[account]).status_code

            with ThreadPoolExecutor(max_workers=4) as pool:
                assert sorted(pool.map(rewrite, ["tester-a"] * 4)) == [200, 200, 429, 429]
            assert rewrite("tester-b") == 200
            assert model.await_count == 3
            os.environ["MAILPOLISH_BETA_INVITES"] = "{}"
            assert client.get("/session", headers=headers["tester-b"]).status_code == 401

    with closing(sqlite3.connect(db)) as conn:
        rows = conn.execute(
            "SELECT account, requests, input_tokens, output_tokens FROM daily_usage ORDER BY account"
        ).fetchall()
    assert rows == [("tester-a", 2, 180, 20), ("tester-b", 1, 90, 10)]
    print("Passed: two-account sign-in, concurrent quota, account isolation, token totals, and revocation.")
