# Forge (Advanced, Multi-Provider, Supabase) — Autonomous AI Coding Agent

> **Forge** is an autonomous coding agent — give it a public GitHub repo and a task in plain English, and it plans, edits, tests, and reports back, live, step by step, inside a hardened, network-isolated container, powered by whichever LLM is available (Claude 3.5 Sonnet primary, Google Gemini Flash free fallback), with managed **Supabase Postgres** persistence.

**Deployment Architecture:**
- **Frontend:** Vercel (Next.js 14 App Router + Tailwind CSS)
- **Backend:** Render (FastAPI + Python) — *no persistent disk needed!*
- **Database:** Supabase Postgres (Managed free relational instance)

---

## 🌟 Key Features

1. **Provider-Agnostic LLM Engine (`LLMProvider`)**:
   - Zero-dependency interface for models (`ClaudeProvider`, `GeminiProvider`).
   - Automatic fallback chain (`claude` &rarr; `gemini-flash`): on rate limits or API key absence, the router seamlessly fails over to the next available provider and logs the switch directly into the step log.
   - Run completely free locally with just a `GEMINI_API_KEY`.

2. **Managed Supabase Postgres Persistence**:
   - Persistence survives backend restarts and redeploys without needing paid Render disks.
   - Resilient connection pooling (`pool_pre_ping=True`, `pool_recycle=300`) optimized for Supabase transaction poolers.
   - Built-in SQLite fallback (`sqlite:///forge.db`) for offline local development.
   - Complete DDL schema script ready to paste into Supabase SQL Editor ([`supabase_schema.sql`](file:///backend/supabase_schema.sql)).

3. **Hardened Sandboxed Execution (`Sandbox`)**:
   - Fresh ephemeral Docker container per run with `--network none`, cgroups 512MB RAM / 1 CPU limits, read-only root with writable repo overlay, and guaranteed cleanup in `finally`.
   - Path containment verification (`validate_path`) blocking path traversal attacks (`../`, null bytes, symlink escapes).
   - Documented subprocess fallback mode with scrubbed environment variables for non-Docker hosts.

4. **Production-Grade Two-Token Authentication**:
   - Short-lived JWT Access Token (15 min) kept exclusively in memory on frontend (XSS immune).
   - Long-lived HttpOnly, Secure, `SameSite=Strict` Refresh Cookie (8 hr) with single-use token rotation and revocation tracking.
   - `X-CSRF-Token` header verification on refresh endpoints.
   - Constant-time password verification via `secrets.compare_digest`.
   - `slowapi` rate limiting (5 attempts/min on `/auth/verify`).

5. **Defense-in-Depth Logging & Security**:
   - Secret redaction filter stripping Anthropic, Gemini, GitHub, and Bearer tokens before writing to database, logs, or SSE streams.
   - Security Headers Middleware: CSP, HSTS, X-Content-Type-Options, X-Frame-Options.
   - Resumable SSE step stream via `Last-Event-ID`.
   - Gated Pull Request creation requiring explicit user review and authorization.

---

## 🏗️ Architecture

```
Forge Frontend (Next.js 14 + Tailwind + TS) — Vercel
   │ POST /auth/verify        { password }        → { access_token, refresh_cookie }
   │ POST /auth/refresh       (cookie + CSRF)     → { access_token }
   │ POST /agent/run          { repo_url, task }   → { run_id }
   │ GET  /agent/stream/{id}  (SSE, Last-Event-ID resumable)
   │ POST /agent/cancel/{id}
   │ POST /agent/{id}/create-pr   (explicit confirm, separate auth check)
   │ GET  /runs               (history, paginated)
   ▼
Forge Backend (FastAPI + Python 3.11/3.12) — Render
   ├── auth.py           → access/refresh token issuance, Depends(verify_token)
   ├── agent_loop.py     → plan → act → observe → reflect cycle
   ├── llm/
   │   ├── provider.py   → abstract LLMProvider interface & schemas
   │   ├── claude.py     → Claude adapter (primary)
   │   ├── gemini.py     → Gemini Flash adapter (free fallback)
   │   └── router.py     → fallback-chain & runtime failover
   ├── tools.py          → tool schemas + dispatch, JSON-Schema validated
   ├── sandbox.py        → ephemeral container isolation + path verification
   ├── github_client.py  → issue lookup & gated PR creation
   ├── context_store.py  → scratchpad with observation sliding window
   ├── logger.py         → SSE broker + audit logger + secret redaction
   ├── db.py             → Supabase Postgres connection pooler + models
   ├── security.py       → security headers, regex redaction, rate limits
   └── main.py           → FastAPI app, exception handlers, /health, /ready
   ▼
Supabase Postgres (Managed Database)
   ├── runs              → persistent run results, status, diffs
   ├── steps             → step-by-step reasoning logs (SSE replay)
   ├── audit_log         → security events, auth attempts, write logs
   └── revoked_tokens    → token rotation blacklist
```

---

## 🗄️ Supabase Postgres Setup (1-Minute Guide)

1. Create a free project at [supabase.com](https://supabase.com).
2. Open the **SQL Editor** in your Supabase project dashboard.
3. Open [`backend/supabase_schema.sql`](file:///backend/supabase_schema.sql), paste the SQL commands, and click **Run**.
4. Go to **Project Settings &rarr; Database &rarr; Connection String**:
   - Select **Mode: Transaction (Port 6543)**.
   - Copy the URI (format: `postgresql://postgres.[REF]:[ENCODED_PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require`).
   - URL-encode special password characters before saving it. For example, `@` becomes `%40`, `#` becomes `%23`, and `%` becomes `%25`.
5. Set `DATABASE_URL` in your backend environment variables (on Render and local `.env`).

---

## 🚀 Quick Start (Local Development)

### 1. Backend Setup

```bash
cd backend
# On Windows:
py -3.11 -m venv venv
.\venv\Scripts\activate
# On Linux/macOS:
python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run FastAPI server with the project interpreter
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local

# Run Next.js development server
npm run dev
```

Visit `http://localhost:3000` and enter the default access code: `forge-dev-secret`.

---

## 🧪 Running Automated Tests

Run the complete test suite:

```bash
cd backend
pytest -v
```

---

## 🔒 Security Principles Verified

- ✅ **No secret leakage**: Regex filter scrubs API keys and Bearer tokens before database writes and SSE broadcast.
- ✅ **Path jail containment**: File tools strictly verify paths stay within sandbox workspace.
- ✅ **No automatic push**: Creating a PR requires separate authenticated confirmation.
- ✅ **Resilient SSE**: Replays missed events on connection drop using `Last-Event-ID`.
- ✅ **Constant-time authentication**: Resistant to timing attacks and brute-forcing via rate limiting.
