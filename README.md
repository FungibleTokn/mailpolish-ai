# MailPolish AI

Chrome extension prototype for one-click professional email rewrites in Gmail, backed by a FastAPI service using OpenAI.

## Structure
- `extension/` — Manifest V3 Gmail content script, toolbar, preview, and service worker
- `backend/` — FastAPI rewrite endpoint
- `dashboard/` — future account dashboard (not yet implemented)

## Start backend
Requires Python 3.11+ and an OpenAI API key.

```bash
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Copy .env.example to .env and set OPENAI_API_KEY plus a unique MAILPOLISH_API_TOKEN
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify `http://localhost:8000/health` returns `{"status":"ok"}`.

## Load extension in Chrome
1. Copy `extension/config.example.js` to `extension/config.js`.
2. Set `apiToken` in `config.js` to the same `MAILPOLISH_API_TOKEN` as the backend.
3. Go to `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the `extension` directory.
4. Open Gmail and compose a message. Click a MailPolish action, review the result, then choose **Replace draft** or **Copy**.
5. Review the draft before sending. The extension never sends email.

## Security and limitations
- **Local prototype only.** The extension development token is visible to anyone who has the extension. Do not distribute it or expose the backend publicly. Production requires per-user login, server-side quotas and rate limiting.
- Email text is sent to the configured backend and OpenAI **only when a rewrite button is clicked**. The application does not persist draft bodies.
- Gmail DOM selectors and replacement behavior are subject to change. Manual browser testing is required.
- Billing, authentication, usage quotas, privacy policy, production deployment, and dashboard are not implemented.
- API keys belong only in backend `.env`, never in the extension or repository.
