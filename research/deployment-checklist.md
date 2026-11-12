# R.I.O. Public Sandbox Validation & Deployment Checklist

> **Current Status:** *Locally production- and full two-container Docker stack-verified (`rio-public-demo:latest` + `rio-public-demo-web:latest`), pending hosted Render verification.* Do not describe the public deployment as production-ready until live Render checks including post-sleep recovery (Section 3) have executed and passed.

---

## 1. Local Validation Summary (Completed)

1. **Unit & Integration Verification (`23 tests`):**
   ```powershell
   pytest apps/public-demo/test_public_demo.py -v
   ```
   Covers AST isolation, deterministic policy overrides, concurrent approval locking, `413` body-size caps, cross-session IP rate limits, Groq fallbacks, Docker/`nginx.conf`/`docker-compose.public-demo.yml`/`render.yaml` checks, and ephemeral restart purge behavior.
2. **Scenario-Based Experiments (`10 runs`, `9 metrics`):**
   ```powershell
   python experiments/scenarios/run_scenarios.py
   python experiments/analysis/analyze_metrics.py
   ```
3. **Human Evaluation:** *Not yet conducted with real participants* (`experiments/human_eval/sample_study_data.json` is strictly a synthetic pipeline-validation fixture).

---

## 2. Docker Build Context & Two-Container Verification (Completed Locally)

Build both isolated public-demo images (`rio-public-demo:latest` from repository root `.` with `apps/public-demo/Dockerfile.dockerignore`, and `rio-public-demo-web:latest` from `./apps/public-demo-web` with `apps/public-demo-web/.dockerignore`):

```powershell
docker build -f apps/public-demo/Dockerfile -t rio-public-demo:latest .
docker build -f apps/public-demo-web/Dockerfile -t rio-public-demo-web:latest ./apps/public-demo-web
```

Verify both images exclude private runtime directories, `.git`, `.env`, and run as non-root users (`appuser` UID `1000` for backend; `nginx` UID `101` for frontend):

```powershell
docker run --rm --entrypoint sh rio-public-demo:latest -c "id -u && ls -la /app"
docker run --rm --entrypoint sh rio-public-demo-web:latest -c "id -u && ls -la /usr/share/nginx/html"
```

Start the hardened full two-container stack (`read_only: true`, `cap_drop: ALL`, `no-new-privileges:true`) using `docker-compose.public-demo.yml` and run `verify_hosted_demo.py`:

```powershell
docker compose -f docker-compose.public-demo.yml up -d --wait

python experiments/deployment/verify_hosted_demo.py `
  --backend-url http://localhost:8000 `
  --frontend-url http://localhost:8080
```

Verify ephemeral restart behavior using the `Restart-persistence check ID` printed at the end of `verify_hosted_demo.py`:

```powershell
docker compose -f docker-compose.public-demo.yml restart public-demo-api

python experiments/deployment/verify_hosted_demo.py `
  --backend-url http://localhost:8000 `
  --frontend-url http://localhost:8080 `
  --verify-purged-session-id <PASTE_SESSION_ID_FROM_PREVIOUS_RUN>

docker logs rio-public-demo-api
docker compose -f docker-compose.public-demo.yml down
```

Verify that container logs contain zero prompt contents, `Authorization` headers, or `GROQ_API_KEY` tokens.

---

## 3. Public Deployment on Render (`render.yaml` Blueprint) & Hosted Security Verification

The repository includes [render.yaml](../render.yaml) at the repo root configuring **only** the two isolated public demo services (`rio-public-demo-api` Docker Web Service + `rio-public-demo-web` Static Site) with `buildFilter` rules ignoring private runtime directories.

When syncing [render.yaml](../render.yaml) on Render:
1. Render auto-wires `VITE_API_BASE_URL` on `rio-public-demo-web` from `rio-public-demo-api`'s `RENDER_EXTERNAL_HOSTNAME` (normalized to `https://` in [api.ts](../apps/public-demo-web/src/api.ts)).
2. Enter your deployed static site origin (e.g., `https://rio-public-demo-web.onrender.com`, never `*`) for `DEMO_ALLOWED_ORIGINS` (`sync: false`) and optionally provide `GROQ_API_KEY` (`sync: false`, or leave blank for deterministic planning).

### Service A: Public Backend (`rio-public-demo-api` — Render Web Service / Docker)
- **Repository / Branch:** `Bala-Mugesh/R.I.O` (`deployment/rio-public-research-sandbox`)
- **Docker Context / Dockerfile Path:** `.` / `apps/public-demo/Dockerfile`
- **Health Check Path:** `/health`
- **Scaling Constraint:** Single container instance / `--workers 1` (default in `Dockerfile`), no Redis or external database.
- **Env vars:** `PYTHONUNBUFFERED=1`, `APP_ENV=production`, `SESSION_TTL_SECONDS=1800`, `DEMO_STEP_DELAY_MS=150`, `DEMO_ALLOWED_ORIGINS=https://YOUR-FRONTEND-URL.onrender.com`, optional `GROQ_API_KEY` & `GROQ_MODEL=llama-3.3-70b-versatile`.

### Single-Instance Architecture Limitations (Intentionally Without Redis)
- Both `InMemorySessionStore` (30-min TTL, max 250 active sessions) and `SlidingWindowRateLimiter` (`req`, `create`, `mutate`, `mutate_ip`) reside in single-process RAM to preserve strict dependency isolation and avoid external Redis/DB coupling.
- Scaling to multiple workers or multiple horizontal replicas would partition session state and per-IP rate-limit counters across processes; keep the Render demo on 1 instance / 1 worker until multi-instance storage is intentionally introduced later.
- All sessions and simulated artifacts reset cleanly on container restart or free-tier sleep (`404` purged).

### Service B: Public Frontend (`rio-public-demo-web` — Render Static Site)
- **Root Directory:** `apps/public-demo-web`
- **Build Command:** `npm ci && npm run build`
- **Publish Directory:** `dist`
- **Env var:** `VITE_API_BASE_URL` (auto-wired from `rio-public-demo-api` via `RENDER_EXTERNAL_HOSTNAME` in `render.yaml`)

### Live Hosted & Post-Sleep Verification

1. Run the hosted security and boundary verifier immediately after deployment:
   ```powershell
   python experiments/deployment/verify_hosted_demo.py `
     --backend-url https://YOUR-BACKEND-URL.onrender.com `
     --frontend-url https://YOUR-FRONTEND-URL.onrender.com `
     --health-timeout 120
   ```
2. Leave the service idle for **>15 minutes** so Render's free tier scales down to sleep.
3. Re-run with the session ID printed by step 1 to verify cold-start wake recovery **and** clean ephemeral purge (`404`) across Render restarts:
   ```powershell
   python experiments/deployment/verify_hosted_demo.py `
     --backend-url https://YOUR-BACKEND-URL.onrender.com `
     --frontend-url https://YOUR-FRONTEND-URL.onrender.com `
     --health-timeout 120 `
     --verify-purged-session-id <PASTE_SESSION_ID_FROM_STEP_1>
   ```
4. Inspect Render service logs to verify zero secrets appear in logs.

---

## 4. Consented Human Evaluation (After Hosted Verification)

> **Integrity Rule:** Never cite [sample_study_data.json](../experiments/human_eval/sample_study_data.json) (`synthetic_validation_fixture: true`) as human participant outcomes in papers, abstracts, or resumes.

For real participants, follow [human-evaluation-protocol.md](./human-evaluation-protocol.md) with informed consent and applicable ethics review, then score collected responses via:

```powershell
python experiments/human_eval/score_human_eval.py path/to/consented_study_data.json
```
