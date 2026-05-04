# Going live for 5–10 testers

The goal is to share **one URL** with your beta users, point them at the chatbot, and have it actually work — backtests run, AI Filter runs, Strategy Finder runs.

For the beta there is **no live data ingest**. The chatbot reads everything out of the parquet files we already built (XAUUSD 5m / 10m / 15m / 30m / 1h / 4h / 1d, ~2 years history, with full SMC + TI features pre-computed). When you onboard real users post-beta, flip on the cron — instructions for that are in [phase2_live_strategy_architecture.md](phase2_live_strategy_architecture.md). Today we keep it simple.

Three deploy options below — pick whichever matches how much infra time you want to spend.

---

## What you need before any deploy

You **must** have these keys ready, otherwise the chatbot is dead:

| Var                       | Required?       | Why                                                     |
|---------------------------|-----------------|---------------------------------------------------------|
| `ANTHROPIC_API_KEY`       | **YES — hard requirement** | Every parse, every code-gen, every Strategy Finder param sweep, every improvement summary, every results summary calls Claude. Without this the app falls back to mock mode and is essentially unusable. |
| `QUANTFLOW_LLM_MODE=claude` | yes           | Locks the app into Claude path; without it the app uses `auto` and silently drops to mock if the key isn't seen. |
| `NEXT_PUBLIC_API_BASE`    | yes (frontend)  | The public URL of your backend service.                 |
| `QUANTFLOW_ALLOWED_ORIGINS` | yes (backend) | The public URL of your frontend (CORS).                 |
| `QUANTFLOW_FINNHUB_KEY`   | **no, for beta** | Only needed when you turn the live-ingest cron back on. The bundled parquet has 2 years of history; that's plenty for backtests. |

**Important:** the only piece of code that calls Claude is on the backend. The Anthropic key never goes to the frontend. Treat it like a database password — env var only, never in git.

The Anthropic key gets billed per token. Strategy Finder is the most expensive call (~$0.05–0.20 per run). Set a monthly cap in the Anthropic console before opening to testers.

---

## Option A — Render (recommended, ~20 minutes, free tier)

Render is the path of least resistance: free tier covers small backends, Git push deploys, no Docker required.

### What you'll create

```
Fresh GitHub repo:  tradexpert-chatbot
    └── only the chatbot/quantflow contents (NOT the whole TradeXpert tree)
        ├── backend/      ← parquet bundled here, source of truth
        ├── frontend/
        └── docs/

Render:
    ├── Web Service: tradexpert-backend (FastAPI on uvicorn, free tier)
    └── Web Service: tradexpert-frontend (Next.js, free tier)
```

That's it — **two services, no cron**. The bar data lives in `backend/data/ohlcv/XAUUSD/*.parquet` and the features in `backend/data/prebuilt_features/XAUUSD_*_smc.parquet`; you commit both to the repo.

**Why a fresh repo, not the whole TradeXpert tree?** The chatbot is fully self-contained at runtime. Pushing the whole `TradeXpert/` repo would drag in `marketapi_data_fetcher/`, `forex_scrapper/`, models, screenshots — none of which the deployed app needs. Slower clones, slower builds, larger surface area for committed secrets. The CSV path in `backfill_xauusd.py` references the parent repo, but that script only runs locally during backfill, never on Render.

### Step 0 — Get your Anthropic key

[console.anthropic.com](https://console.anthropic.com) → **API Keys** → Create key (`sk-ant-...`). Save it. Then **Settings → Billing → Spend caps** → set a $20/month cap so 10 testers can't blow up your bill.

### Step 1 — Build the new repo locally

```bash
mkdir ~/tradexpert-chatbot && cd ~/tradexpert-chatbot

# copy ONLY chatbot/quantflow contents (note the trailing /*)
cp -r /c/TradeXpert/TradeXpert/chatbot/quantflow/* .
cp -r /c/TradeXpert/TradeXpert/chatbot/quantflow/.[!.]* . 2>/dev/null  # any dotfiles

ls   # should show: backend/  frontend/  docs/  README.md
```

### Step 2 — Add a `.gitignore`

```bash
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Node
node_modules/
.next/
*.tsbuildinfo

# Local DB / env
*.db
*.db-journal
.env
.env.local
.env.*.local

# Logs
*.log
backend/_server.*.log

# Editor
.vscode/
.idea/
.DS_Store

# Build artifacts
frontend/public/quantflow-tw.css
EOF
```

### Step 3 — Verify the parquet files are there

```bash
ls backend/data/ohlcv/XAUUSD/         # 1m.parquet ... 1d.parquet
ls backend/data/prebuilt_features/    # XAUUSD_*_smc.parquet
du -sh backend/data/                  # ~50–80 MB total
```

If empty, copy from your dev tree:
```bash
cp -r /c/TradeXpert/TradeXpert/chatbot/quantflow/backend/data/ohlcv backend/data/
cp -r /c/TradeXpert/TradeXpert/chatbot/quantflow/backend/data/prebuilt_features backend/data/
```

### Step 4 — Push to GitHub

```bash
git init
git add .
git status                       # eyeball: no .env, no *.db, no node_modules
git commit -m "Initial chatbot repo with bundled XAUUSD 2y bars + features"

# create empty private repo on github.com/new (name: tradexpert-chatbot)
git remote add origin git@github.com:<you>/tradexpert-chatbot.git
git branch -M main
git push -u origin main
```

If GitHub rejects a single file >100 MB (unlikely — `5m_smc.parquet` is ~18 MB):
```bash
git lfs install
git lfs track "backend/data/**/*.parquet"
git add .gitattributes && git commit -m "Track parquet via LFS"
git push -u origin main
```

### Step 5 — Deploy the backend

[Render](https://render.com) → sign in → **New → Web Service** → connect `tradexpert-chatbot`:

| Field             | Value                                                                    |
|-------------------|--------------------------------------------------------------------------|
| Name              | `tradexpert-backend`                                                     |
| Region            | Closest to you (Oregon for US, Frankfurt for EU)                          |
| Branch            | `main`                                                                    |
| Root directory    | `backend`                                                                 |
| Runtime           | Python 3                                                                  |
| Build command     | `pip install -r requirements.txt`                                        |
| Start command     | `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --app-dir ..`  |
| Instance type     | Free                                                                      |

**Environment variables** (Advanced → Add Environment Variable, four entries):

| Key                          | Value                                  |
|------------------------------|----------------------------------------|
| `ANTHROPIC_API_KEY`          | `sk-ant-...` (your key)                |
| `QUANTFLOW_LLM_MODE`         | `claude`                               |
| `QUANTFLOW_RELOAD`           | `false`                                |
| `QUANTFLOW_ALLOWED_ORIGINS`  | `*` *(temporary — locked down in step 7)* |

Click **Create Web Service**. Wait ~5 min for first build. Copy the URL when live (e.g. `https://tradexpert-backend-xxxx.onrender.com`).

```bash
curl https://tradexpert-backend-xxxx.onrender.com/health
# expect: {"status":"ok","llm_mode":"claude"}    ← MUST be "claude", not "mock"
```

### Step 6 — Deploy the frontend

**New → Web Service** → same repo:

| Field             | Value                                       |
|-------------------|---------------------------------------------|
| Name              | `tradexpert-frontend`                       |
| Branch            | `main`                                       |
| Root directory    | `frontend`                                   |
| Runtime           | Node                                         |
| Build command     | `npm install && npm run build`              |
| Start command     | `npm start`                                  |
| Instance type     | Free                                         |

**Environment variables**:

| Key                       | Value                                                            |
|---------------------------|------------------------------------------------------------------|
| `NEXT_PUBLIC_API_BASE`    | `https://tradexpert-backend-xxxx.onrender.com` (from step 5)     |
| `NODE_ENV`                | `production`                                                     |

Click **Create Web Service**. Wait ~5 min. Copy the frontend URL.

### Step 7 — Lock down CORS

Backend service → **Environment** → edit `QUANTFLOW_ALLOWED_ORIGINS`:
```
https://tradexpert-frontend-xxxx.onrender.com
```
(no trailing slash, exact match). **Save Changes** — auto-redeploys.

### Step 8 — End-to-end smoke test

Open the frontend URL:

1. Welcome hero loads.
2. Type `EMA 9 21 cross on XAUUSD 5m` → bot asks "How far back should I run the backtest?"
3. Reply `last 6 months` → backtest card renders with metrics + equity curve.
4. Click **Apply AI Filter** → completes in ~10–30s (features are bundled, no recompute).
5. Click **Run Strategy Finder** → Claude proposes ranges → click **Run Optimization** → finder card renders.

If anything 500s, Render → backend → **Logs** has the Python traceback. The two recurring causes are missing env vars (Anthropic key) and missing parquet on disk (forgot to commit).

### Step 9 — Share

`https://tradexpert-frontend-xxxx.onrender.com` is the URL you hand to testers.

### Costs

- Render free tier covers both web services. Paid Starter is $7/mo per service if you outgrow it.
- Free services spin down after 15 min of inactivity → first request after a quiet hour takes ~30s while the container cold-starts. Acceptable for a 10-tester demo.
- **Anthropic:** budget $5–20/month for 5–10 active testers. Strategy Finder is the most expensive call (~$0.10 each). The spend cap you set in step 0 is the safety net.

### Optional: persistent SQLite for chat history

By default the chats DB lives in the container's ephemeral filesystem and is wiped on every redeploy. To keep chats across deploys, on the backend service: **Disks → Add Disk** (1 GB) at `/opt/render/project/data`, then add env var `QUANTFLOW_DATABASE_URL=sqlite:////opt/render/project/data/quantflow.db`. Skip this for the very first launch — testers will just create new chats anyway.

---

## Option B — Single VM (DigitalOcean / Hetzner / Lightsail, $5–7/month)

Right answer when you outgrow Render's free tier or want a stable always-on box without spin-down latency. ~30 min one-off setup.

```bash
# 1. spin up an Ubuntu 22.04 droplet, SSH in
ssh root@<ip>
apt update && apt install -y python3.11-venv nodejs npm nginx certbot python3-certbot-nginx git git-lfs

# 2. clone (with LFS so the parquet pulls down)
git lfs install
git clone https://github.com/<you>/TradeXpert.git
cd TradeXpert/chatbot/quantflow

# 3. set up venv + deps
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..

# 4. set env
cat > .env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
QUANTFLOW_LLM_MODE=claude
QUANTFLOW_HOST=0.0.0.0
QUANTFLOW_RELOAD=false
NEXT_PUBLIC_API_BASE=https://<your-domain>
QUANTFLOW_ALLOWED_ORIGINS=https://<your-domain>
EOF

# 5. install systemd units (snippets below) — backend + frontend only, no ingest cron
# 6. nginx reverse proxy on :443 → backend :8000 + frontend :3000
# 7. certbot for TLS
```

**systemd units** (drop into `/etc/systemd/system/`):

```ini
# tradexpert-backend.service
[Unit]
Description=TradeXpert backend (FastAPI)
After=network.target

[Service]
WorkingDirectory=/root/TradeXpert/chatbot/quantflow
EnvironmentFile=/root/TradeXpert/chatbot/quantflow/.env
ExecStart=/root/TradeXpert/chatbot/quantflow/.venv/bin/uvicorn \
    backend.api.main:app --host 0.0.0.0 --port 8000 --app-dir /root/TradeXpert/chatbot/quantflow
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# tradexpert-frontend.service
[Unit]
Description=TradeXpert frontend (Next.js)
After=network.target

[Service]
WorkingDirectory=/root/TradeXpert/chatbot/quantflow/frontend
EnvironmentFile=/root/TradeXpert/chatbot/quantflow/.env
ExecStart=/usr/bin/npm start
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now tradexpert-backend tradexpert-frontend
```

**nginx** (`/etc/nginx/sites-available/tradexpert`):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }

    # backend
    location /chats { proxy_pass http://127.0.0.1:8000; proxy_read_timeout 1200s; proxy_set_header Host $host; }
    location /strategies { proxy_pass http://127.0.0.1:8000; proxy_read_timeout 1200s; proxy_set_header Host $host; }
    location /health { proxy_pass http://127.0.0.1:8000; }
}
```

```bash
ln -s /etc/nginx/sites-available/tradexpert /etc/nginx/sites-enabled/
certbot --nginx -d your-domain.com   # automatic TLS
nginx -s reload
```

Total monthly cost: $6 (Hetzner CX11) or $7 (DO basic) plus the Anthropic spend.

---

## Option C — ngrok tunnel (5 min, for ad-hoc demos only)

If you just want to show one person your local machine right now:

```bash
# terminal 1
cd chatbot/quantflow && python backend/run.py
# terminal 2
cd chatbot/quantflow/frontend && npm run dev
# terminal 3
ngrok http 8000   # gives you a public https://xxx.ngrok-free.app for the BACKEND
# terminal 4
ngrok http 3000   # second tunnel for the FRONTEND
```

In `frontend/.env.local`:
```
NEXT_PUBLIC_API_BASE=https://<backend-tunnel>.ngrok-free.app
```

**Don't use this for real testers.** Your laptop sleeping kills the URL, the free tier rotates the subdomain on every restart, and you're paying laptop electricity bills to host strangers.

---

## Pre-flight before sharing the URL

- [ ] `ANTHROPIC_API_KEY` is set on the backend service (no key = no Claude = unusable app).
- [ ] `QUANTFLOW_LLM_MODE=claude` is set.
- [ ] `NEXT_PUBLIC_API_BASE` on the frontend points at the public backend URL (https://, not http://).
- [ ] `QUANTFLOW_ALLOWED_ORIGINS` on the backend includes the frontend URL exactly (no trailing slash).
- [ ] `backend/data/ohlcv/XAUUSD/*.parquet` files are present in the deployed slug (committed via git).
- [ ] `backend/data/prebuilt_features/XAUUSD_*_smc.parquet` files are present too — without these, AI Filter takes 5+ minutes per request.
- [ ] `curl https://<backend>/health` returns `{"status":"ok","llm_mode":"claude"}` (must be `claude`, not `mock`).
- [ ] You ran an end-to-end test on the public frontend URL (parse → backtest → AI Filter → Strategy Finder).
- [ ] Anthropic monthly spend cap is set in the Anthropic console.

If any of those fail, fix before sharing — testers silently quit on the first 500.

---

## When to graduate from this setup

The Option A / B setup carries you to maybe ~50 concurrent users. Past that, the things that break in this order:

1. **Stale prices.** Parquet was frozen at backfill time → turn on the ingest cron (`python -m backend.ingest.runner --loop --every 60`) so bars stay current.
2. **SQLite locks** under concurrent writes → switch to Postgres (one env var).
3. **One container running both ingest + API** → split them, share a small Postgres / Redis instead of disk.
4. **Free Finnhub tier rate-limiting** → upgrade to paid tier or switch to Polygon.io.
5. **Anthropic spend** → cache parsed strategies and start using prompt caching.

That's the next conversation, not this one. For the 5–10 tester launch, Option A in Render with the bundled parquet works tonight.
