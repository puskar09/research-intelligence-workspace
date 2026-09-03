# Setup Guide — Research Intelligence Workspace

> **For full architecture, features, engineering decisions, evaluation, and roadmap see [`README.md`](README.md).**

---

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Git | any | Clone the repo |
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| Docker & Docker Compose | any | PostgreSQL + pgvector database |
| Anthropic API key | — | LLM synthesis (research queries) |
| Google Gemini API key | — | Alternative/supplementary LLM |

At least one LLM API key (**`ANTHROPIC_API_KEY`** is the default used by the research pipeline) is required for research queries. PDF ingestion and embedding work without any API key.

---

## 1. Clone the Repository

```bash
git clone https://github.com/puskar09/research-intelligence-workspace.git
cd research-intelligence-workspace
```

---

## 2. Environment Variables

### Backend `.env`

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set:

```dotenv
# ── PostgreSQL (defaults match docker-compose.yml — change only if needed) ──
POSTGRES_DB=riw
POSTGRES_USER=riw_user
POSTGRES_PASSWORD=riw_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# ── LLM providers ──────────────────────────────────────────────────────────
# REQUIRED for research queries (used by the research & RAG endpoints)
ANTHROPIC_API_KEY=your-anthropic-api-key-here
CLAUDE_MODEL=claude-sonnet-5           # must be set — no default fallback

# OPTIONAL — used by /api/rag endpoints (Gemini alternative)
GOOGLE_API_KEY=your-google-api-key-here
# LLM_MODEL=gemini-3.6-flash          # optional model override
```

**Required vs Optional summary:**

| Variable | Required? | Notes |
|---|---|---|
| `POSTGRES_DB` | Required | Default: `riw` |
| `POSTGRES_USER` | Required | Default: `riw_user` |
| `POSTGRES_PASSWORD` | Required | Default: `riw_password` |
| `POSTGRES_HOST` | Required | Default: `localhost` (local) |
| `POSTGRES_PORT` | Required | Default: `5432` |
| `ANTHROPIC_API_KEY` | **Required** for research | No default — app errors without it |
| `CLAUDE_MODEL` | **Required** for research | e.g. `claude-sonnet-5` |
| `GOOGLE_API_KEY` | Optional | Only needed for `/api/rag` endpoints |
| `LLM_MODEL` | Optional | Overrides default Gemini model |

> The `.env` file is gitignored. Never commit it.

---

## 3. Start the Database

The project ships a `docker-compose.yml` that runs **PostgreSQL 16 with the `pgvector` extension** inside Docker. The backend itself runs locally (outside Docker) by default.

```bash
# Start only the database (recommended for local development)
docker compose up -d postgres

# Verify it is healthy
docker compose ps
```

The database is exposed on **port 5432** and data is stored in the `riw_pgdata` Docker volume (survives restarts).

```bash
# Stop (keeps data)
docker compose down

# Stop AND delete all data
docker compose down -v
```

> Alternatively, run both the database and backend inside Docker:
> ```bash
> docker compose up -d --build
> ```
> The containerised backend runs on **port 8001** (mapped from the container).

---

## 4. Run the Backend (locally)

Run these commands from the **repository root** (not from `backend/` — the package is imported as `backend.main`):

```bash
# Create and activate a virtual environment
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn backend.main:app --reload --port 8001
```

On first start the backend will:
1. Initialise the PostgreSQL schema (creates tables, enables `pgvector`).
2. Download and load the `all-MiniLM-L6-v2` embedding model (~90 MB from HuggingFace, cached locally after first run).

**Verify it is running:**
```bash
curl http://localhost:8001/health
# Expected: {"status": "ok"}
```

The interactive API docs are available at `http://localhost:8001/docs`.

---

## 5. Run the Frontend (locally)

Open a **new terminal** from the repository root:

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on **`http://localhost:3000`**.

### Local `BACKEND_API_URL` configuration

For local development you do **not** need to set `BACKEND_API_URL`. The Next.js rewrite in `frontend/next.config.ts` automatically proxies all `/api/backend/*` requests to `http://127.0.0.1:8001/api` when running locally.

If you need to override (e.g. point a local frontend at a remote backend):

```bash
# Create frontend/.env.local
echo "BACKEND_API_URL=http://127.0.0.1:8001/api" > frontend/.env.local
```

---

## 6. Test the System

Open `http://localhost:3000` in your browser.

### PDF-only research
1. Click **Upload PDF** and select any PDF.
2. Wait for the success confirmation (ingestion + embedding is synchronous for the DB write; embedding runs in the background).
3. In the **Ask** tab, type a question about the PDF content.
4. Make sure **"Search the web"** is toggled **off**.
5. Click **Ask**. The answer will cite specific page numbers from your PDF.

### Web-only research
1. Do not upload any PDF (or ignore existing uploads).
2. In the **Research** tab, type a question on any live topic.
3. Toggle **"Search the web"** **on**.
4. Click **Research**. Findings will cite live web URLs.

### PDF + Web combined research
1. Upload one or more PDFs.
2. Toggle **"Search the web"** **on**.
3. Run a research query. The system retrieves from both local documents and the web, ranks all evidence together using cosine similarity, and synthesises a structured report with explicit "Insufficient Evidence" flags where data is missing.

---

## 7. Production Deployment

### 7a. Railway — Backend

1. **Create a new Railway project** and add a **PostgreSQL** service. Copy the connection variables from Railway's PostgreSQL service dashboard into your backend service's Variables tab.

2. **Connect your GitHub repository** to a new Railway service. Configure:
   - **Root Directory**: `/` (repo root)
   - **Dockerfile Path**: `backend/Dockerfile`

3. **Set environment variables** in the Railway service Variables tab:

   | Variable | Value |
   |---|---|
   | `POSTGRES_HOST` | Internal hostname from Railway PostgreSQL service |
   | `POSTGRES_DB` | From Railway PostgreSQL service |
   | `POSTGRES_USER` | From Railway PostgreSQL service |
   | `POSTGRES_PASSWORD` | From Railway PostgreSQL service |
   | `POSTGRES_PORT` | `5432` |
   | `ANTHROPIC_API_KEY` | Your Anthropic key |
   | `CLAUDE_MODEL` | e.g. `claude-sonnet-5` |
   | `GOOGLE_API_KEY` | Your Google key (required for `/api/rag` endpoints) |

4. **`$PORT` and Target Port**: Railway injects `$PORT=8080` automatically. The backend Dockerfile reads it:
   ```dockerfile
   CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 75"
   ```
   In Railway → Service → Settings → Networking, set **Target Port to `8080`**. This must match `EXPOSE 8080` in `backend/Dockerfile`.

5. **Verify the deployment** after Railway finishes building (~5–10 min):
   ```bash
   curl https://your-backend.up.railway.app/health
   # Expected: {"status": "ok"}
   ```

   > **Note**: The first deploy downloads `all-MiniLM-L6-v2` from HuggingFace on startup (60–90 seconds). Railway logs will show `Database ready.` then `Application startup complete.` when fully ready.

---

### 7b. Vercel — Frontend

1. **Import your GitHub repository** into Vercel. Set the **Root Directory** to `frontend`.

2. **Add the following Build Environment Variable** in Vercel → Project → Settings → Environment Variables:

   | Variable | Value | Scope |
   |---|---|---|
   | `BACKEND_API_URL` | `https://your-backend.up.railway.app/api` | **Build** (not runtime) |

   > **Critical**: `BACKEND_API_URL` is evaluated at `next build` time and baked into the routing manifest (`routes-manifest.json`). It **must** be a Build variable. Do **not** include a trailing slash. If it is missing at build time, Vercel bakes `http://127.0.0.1` as the destination and every proxy request returns `502 ROUTER_EXTERNAL_TARGET`.

3. Vercel runs `npm run build` and deploys automatically on each push to `main`.

4. The request flow after deployment:
   ```
   Browser → POST /api/backend/sources/pdf
     → Vercel Next.js rewrite
     → https://your-backend.up.railway.app/api/sources/pdf
     → Railway FastAPI → {"source": ..., "chunks": [...]}
   ```

---

## 8. Troubleshooting

### Railway 502 `"Application failed to respond"`

| Cause | Fix |
|---|---|
| **Target Port mismatch** | Railway → Service → Settings → Networking → set Target Port to `8080` |
| **Cold-start timeout** | Wait ~90 s after deployment for the model to load, then retry |
| **Missing DB env vars** | Check Railway logs for `OperationalError`; ensure all `POSTGRES_*` vars are set |
| **Missing `CLAUDE_MODEL`** | Logs will show `LLMServiceError`; set `CLAUDE_MODEL` in Railway Variables |

### Vercel `502 ROUTER_EXTERNAL_TARGET`

| Cause | Fix |
|---|---|
| `BACKEND_API_URL` not set at build time | Add it as a **Build** env var in Vercel, then trigger a full Redeploy |
| Trailing slash in `BACKEND_API_URL` | The value is normalised automatically — but avoid it anyway |
| Vercel deployed a stale build | Force redeploy from Vercel dashboard after setting the variable |

### Invalid API key / `503 Research service unavailable`

Both `ANTHROPIC_API_KEY` **and** `CLAUDE_MODEL` must be set. `CLAUDE_MODEL` has **no default** — the service will refuse to initialise and return `503` on every research request if it is missing.

### HuggingFace model download fails at startup

The `all-MiniLM-L6-v2` model is downloaded from HuggingFace on the first start. Ensure the Railway container has outbound internet access. Once downloaded it is cached in `~/.cache/huggingface` inside the container for that deployment lifecycle.

---

## 9. Further Reading

See [`README.md`](README.md) for the full architecture diagram, complete feature list, tech stack table, evaluation suite, learning outcomes, and project roadmap.
