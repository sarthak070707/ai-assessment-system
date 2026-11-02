# Deploying

Backend on Render, frontend on Vercel. Both free tiers.

There is a chicken-and-egg step: the backend needs the frontend's URL for CORS,
and the frontend needs the backend's URL to reach the API. Deploy the backend
first, wire the frontend to it, then come back and tell the backend about the
frontend.

---

## 1. Backend — Render

Push to GitHub, then on Render: **New → Blueprint**, point it at the repo. It
reads `render.yaml` and creates a web service plus a free Postgres database.

Deploying by hand instead:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `./start.sh` |
| Health check path | `/api/health` |

Environment variables:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `JWT_SECRET` | 40+ random characters — see below |
| `DATABASE_URL` | the Postgres internal connection string |
| `ALLOWED_ORIGINS` | the Vercel URL, added in step 3 |
| `GROQ_API_KEY` | optional; without it import falls back to pattern matching and syllabus generation is unavailable |

Generate a secret with:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

With `ENVIRONMENT=production` the service **refuses to start** without one,
rather than falling back to the placeholder in this repository. That placeholder
is public: anyone could forge a token for any account, including the exam
office.

`start.sh` runs `seed.py` on every boot. It writes nothing when the database
already has users, so restarts are safe — but it means a fresh deployment comes
up with an exam office account instead of no way in at all.

Check it came up: `https://your-service.onrender.com/api/health` should report
`"environment": "production"`.

## 2. Frontend — Vercel

**New Project**, same repo.

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework | Vite (detected) |

One environment variable:

    VITE_API_URL = https://your-service.onrender.com

No trailing slash. Vite inlines this **at build time**, so changing it later
needs a redeploy, not just a restart.

## 3. Close the loop

Back on Render, set `ALLOWED_ORIGINS` to the Vercel URL:

    ALLOWED_ORIGINS=https://your-app.vercel.app

Without this the browser blocks every API call and the site looks broken while
the backend logs nothing wrong — the request never arrives.

## 4. Check

1. Open the Vercel URL. The landing page loads.
2. Sign in at `/#/admin` as `EXO001` / `control123`.
3. **Candidates** → select a student → **Generate codes**.
4. Sign out, **Sit an exam**, use that enrolment number and code.

---

## What the free tier costs you

**The backend sleeps after 15 minutes idle.** The first request after that takes
30–60 seconds while it wakes. A visitor may well think it is broken, so the
landing page says so.

**Free Postgres expires after 30 days.** Create a new one and redeploy; seeding
runs automatically on the next boot.

**`VITE_API_URL` is baked into the build.** Moving the backend means rebuilding
the frontend, not just editing a variable.

## Before going public

`frontend/src/components/DemoCredentials.jsx` publishes working staff logins.
That is right for a portfolio link and wrong for anything real — set `SHOW` to
`false` at the top of that file.
