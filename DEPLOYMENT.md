# Deploying Forge — Vercel (Frontend) + Render (Backend) + Supabase (DB)

This guide walks through deploying Forge with the official architecture:

```
Browser
   │  https://forge.vercel.app
   ▼
Vercel (Next.js 14 frontend)
   │  https://forge-backend.onrender.com  (direct HTTPS calls)
   ▼
Render (FastAPI backend, Python 3.11)
   │  postgresql+psycopg2://... @ supabase pooler
   ▼
Supabase Postgres
```

Files created for you:

| File                          | Purpose                                                        |
|-------------------------------|----------------------------------------------------------------|
| `backend/.env.production`     | Source of truth for the backend env — copy its values into Render |
| `frontend/.env.production`    | Source of truth for the frontend env — copy into Vercel          |
| `render.yaml`                 | Render Blueprint — auto-creates the backend web service          |
| `vercel.json`                 | Pins framework/build settings for Vercel                         |

> All values from your local env files are already present in the
> `.env.production` files. These production files are gitignored — keep them
> that way; secrets must never be committed.

---

## 1. Supabase Postgres (5 minutes)

1. Create a free project at https://supabase.com.
2. Open the **SQL Editor**, paste [`backend/supabase_schema.sql`](backend/supabase_schema.sql), click **Run**.
3. Go to **Settings → Database → Connection string**:
   - Mode: **Transaction** (port `6543`) or **Session** (port `5432`).
   - Copy the **Session pooler (IPv4)** string.
4. **Important for this project:** the password contains `@` and `?`.
   Percent-encode them so SQLAlchemy can parse the URL:
   `@` → `%40`, `?` → `%3F`.

   | Raw (broken for SQLAlchemy) | Encoded (use this) |
   |---|---|
   | `postgresql://postgres:GLdz6@5zqQ5f?DX@db...:5432/postgres` | `postgresql://postgres:GLdz6%405zqQ5f%3FDX@aws-0-<REGION>.pooler.supabase.com:5432/postgres` |

   (If your production Supabase project uses a different password, encode it the same way.)

5. **⚠️ Use the SESSION POOLER host, not the direct host.** The direct host
   `db.<project-ref>.supabase.co` is **IPv6-only** on Supabase's free tier.
   Render's containers have **no IPv6 route**, so the API crashes at startup
   with:
   ```
   sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) ... Network is unreachable
   ```
   The fix is the IPv4 session pooler:
   ```
   postgresql+psycopg2://postgres.<PROJECT-REF>:<ENCODED-PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres
   ```
   For this project (replace `REGION` with yours from the dashboard):
   ```
   postgresql+psycopg2://postgres.omwsfhoqyuvpphwrelns:GLdz6%405zqQ5f%3FDX@aws-0-<REGION>.pooler.supabase.com:5432/postgres
   ```
   > ✅ Verified: `aws-0-us-east-1.pooler.supabase.com` is **reachable** (IPv4),
   > but returns `tenant/user postgres.omwsfhoqyuvpphwrelns not found` — so the
   > region must match **your** project; copy it from the dashboard string.
   Get your exact host (region) from **Supabase Dashboard → Connect →
   Session pooler**; it looks like `aws-0-<region>.pooler.supabase.com`.
   (_You cannot run the Db from Render over IPv6 — always use the pooler._)

---

## 2. Render — Backend

### Option A: Blueprint (recommended)

1. Push the repo to GitHub.
2. Render Dashboard → **New → Blueprint**.
3. Pick the repo — Render auto-detects `render.yaml` and creates the
   `forge-backend` web service.
4. After the first deploy, open the service → **Environment** tab and fill the
   secrets marked `sync: false` (values are in `backend/.env.production`):
   - `ACCESS_PASSWORD`, `ACCESS_TOKEN_SECRET`, `REFRESH_TOKEN_SECRET`
   - `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`
   - `GITHUB_TOKEN`
   - `DATABASE_URL` ← the encoded Supabase string from step 1
5. Save → Render redeploys.

### Option B: Manual

1. Render Dashboard → **New → Web Service**.
2. Connect your repo; set:
   - Root Directory: `.`
   - Runtime: `Python 3`
   - Build Command: `pip install --no-cache-dir -r backend/requirements.txt`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Instance Type: Free (or Starter)
   - Health Check Path: `/health`
3. Expand **Environment** and add **every** key from `backend/.env.production`.

### Verify the backend

```
https://forge-backend.onrender.com/health   -> {"status":"ok", ...}
https://forge-backend.onrender.com/ready    -> {"status":"ready","database":"connected",...}
https://forge-backend.onrender.com/docs     -> 404 (DEBUG=false hides docs)
```

### Render notes / gotchas

- **No Docker sandbox:** Render has no Docker daemon inside the web service, so
  keep `ENABLE_DOCKER_SANDBOX=false`. Runs use the scrubbed subprocess fallback
  (`backend/sandbox.py`), which needs `git` — Render's Python image ships it.
- **Free instance sleep:** on the Free plan the backend spins down after ~15 min
  of inactivity; the first request after a sleep takes ~30-60s to cold-start.
  The frontend's automatic token-refresh on the first 401 handles the blip.
     Upgrade to Starter for consistent sub-second latency.
  - **Health checks:** `healthCheckPath: /health` keeps the instance marked healthy.

  ---

  ## 3. Vercel — Frontend

1. Vercel Dashboard → **Add New → Project**, import the same repo.
2. Root Directory: `frontend`.
3. Vercel auto-detects Next.js (`vercel.json` pins `nextjs` + build command).
4. **Settings → Environment Variables → Production** (check *Preview* too):
   - `NEXT_PUBLIC_API_BASE_URL = https://forge-backend.onrender.com`
     (your real Render URL, **no trailing slash**)
5. Deploy. Then grab your domain, e.g. `https://forge-agent.vercel.app`.

### After deploying, update the backend CORS origin

Back in Render → `forge-backend` → **Environment**:
set `ALLOWED_ORIGIN = https://forge-agent.vercel.app` (exact Vercel domain).
Render redeploys; verify CORS headers:

```
curl -i -X OPTIONS https://forge-backend.onrender.com/health \
  -H "Origin: https://forge-agent.vercel.app" \
  -H "Access-Control-Request-Method: GET"
# expect: access-control-allow-origin: https://forge-agent.vercel.app
```

### Vercel notes / gotchas

- `NEXT_PUBLIC_*` vars are inlined at **build time** — after changing them, trigger
  a redeploy (don't wait for an auto-redeploy).
- The `/api/*` proxy in `frontend/next.config.mjs` now points at
  `NEXT_PUBLIC_API_BASE_URL` instead of hardcoded `localhost:8000`, so
  `AnalyticsDashboard`'s relative fetches (`/api/analytics/...`) work in
     production. The rest of the app calls the Render backend directly.

  ---

  ## 4. Auth cookies — the important production subtlety

Forge stores the refresh token in an **httpOnly cookie**, and in production the
frontend calls the backend cross-origin (`forge.vercel.app` → `forge-backend.onrender.com`).
What was handled and why:

1. ✅ `ALLOWED_ORIGIN = https://forge-agent.vercel.app` must be set on Render
   (CORS allows the cross-origin calls; `api.ts` sends `credentials: "include"`).
2. ✅ `secure=not settings.DEBUG` — with `DEBUG=false` on Render the cookies get
   the `Secure` flag automatically.
3. ✅ **`SameSite` — already fixed in code.** With `SameSite=Strict`, browsers
   treat a cross-site `fetch()` as third-party and never attach the cookie, so
   `/auth/refresh` would return `401 Missing refresh cookie`. All 8 cookie blocks
   in `backend/routes/auth_routes.py` (`/verify`, `/register`, `/login`,
   `/refresh` × 2 cookies each) now use:

```python
        samesite="none" if not settings.DEBUG else "strict",
```

   So local dev keeps `strict`, and production (DEBUG=false, HTTPS, `Secure`
   flag set) behaves as `SameSite=None` — which is exactly what `SameSite=None`
   requires to be accepted by browsers.

> The access token stays in memory on the frontend (`frontend/src/lib/api.ts`),
> so only the cookie-bearing endpoints are affected.

---

## 5. Post-deploy smoke test

1. Open `https://forge-agent.vercel.app` → enter `ACCESS_PASSWORD` → logged in.
2. Trigger an agent run on a small public repo; confirm the live step feed (SSE)
   streams from the Render backend.
3. Close the tab, reopen within 8 hours → session should auto-refresh
   (verifies the `SameSite=None` change worked).
4. Check Render logs for auth/SSE/DB errors and confirm `/ready` reports
   `database: connected`.

---

## 6. Local dev quick reference

These env files were **not** changed by this setup — they keep working as before:

- `backend/.env` (local dev, loaded by `config.py`)
- `frontend/.env.local` (local dev, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`)

To run a production-mode build locally before pushing:

```bash
# backend
cd backend
set DEBUG=false
uvicorn main:app --host 0.0.0.0 --port 8000

# frontend (uses frontend/.env.production because NODE_ENV=production)
cd frontend
npm run build && npm start
```