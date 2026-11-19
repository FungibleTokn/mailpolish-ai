# MailScribe

MailScribe rewrites Gmail drafts through a FastAPI backend and OpenAI.

## Invite-only beta

Each tester signs in through the Chrome extension popup with an individual invite key. Generate a key and its SHA-256 digest on a trusted device:

```sh
python -c "import hashlib, secrets; key = secrets.token_hex(32); print('Invite key:', key); print('SHA-256:', hashlib.sha256(key.encode()).hexdigest())"
```

Share each key with its tester through a private channel. Store only digests and stable, opaque account IDs in the backend's `MAILPOLISH_BETA_INVITES` variable, as a JSON object such as `{"<digest>":"tester-a"}`. Remove a digest to revoke a key. Keep the account ID when replacing a key so its quota history carries over.

Use a single Railway replica and a persistent volume mounted at `/data`. Set `MAILPOLISH_USAGE_DB=/data/mailpolish-usage.sqlite3`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL` (default `gpt-4o-mini`) and `MAILPOLISH_DAILY_LIMIT` (default 20). The quota resets at midnight UTC. A request reserves a slot before calling OpenAI, including requests that fail upstream. The usage database stores account IDs, request counts, and token totals without storing drafts.

Deploy from `/backend` with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Keep all plaintext credentials out of the repository and extension bundle. The backend URL in the extension is set in `extension/api-config.js` and `extension/manifest.json`.

Load `extension` as an unpacked Chrome extension. Open its popup, sign in with an invite key, refresh Gmail, and try a MailScribe action on a dummy draft. Chrome clears the extension session when the browser restarts. Draft text is sent to the backend and OpenAI when a rewrite is requested. The extension never sends email.

## Local backend test

With Python 3.11 or later, install `backend/requirements.txt`, then run `python backend/test_beta_flow.py` from the repository root. The test uses two generated keys, a temporary SQLite database, and a mocked OpenAI response.

## Google sign-in setup

Create a Google OAuth web application client. Register the backend URL ending in `/auth/google/callback` as its authorized redirect, then set `MAILSCRIBE_GOOGLE_REDIRECT_URI` to that exact URL. Set `MAILSCRIBE_CHROME_REDIRECT_URI` to `https://<extension-id>.chromiumapp.org/google` for the installed build. The Chrome Web Store assigns the store listing ID after the first upload. A staging build can use its own unpacked ID and Railway environment.

Set the client ID and secret in `MAILSCRIBE_GOOGLE_CLIENT_ID` and `MAILSCRIBE_GOOGLE_CLIENT_SECRET`. Generate an independent random `MAILSCRIBE_AUTH_SECRET` of at least 32 characters. Store these values on the backend. The extension contains no OAuth client secret. Set `MAILSCRIBE_GOOGLE_ACCOUNTS` to a JSON object mapping lowercase invited Google email addresses to stable MailScribe account IDs. The app requests only Google identity and email scopes. Google sign-in sessions expire after eight hours. Existing invite keys remain usable during migration. Keep account IDs consistent across both methods to share usage quotas. The first successful Google sign-in binds the account ID to Google’s stable subject identifier. Reassigning a beta account to a different Google identity requires a new account ID.
