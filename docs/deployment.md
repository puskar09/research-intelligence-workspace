# Deployment Guide

The Research Intelligence Workspace is designed to be easily deployed to production using Docker and modern PaaS providers like Railway.

---

## Local Docker Deployment

The repository includes a `docker-compose.yml` file designed to run the PostgreSQL vector database and (optionally) the backend API.

### Starting the Database
To run just the database (useful when running the FastAPI app directly via your IDE/terminal):
```bash
docker compose up -d db
```
This starts PostgreSQL 16 with the `pgvector` extension enabled on port `5432`.

### Starting the Full Backend Stack
To build and run the entire backend via Docker:
```bash
docker compose up -d --build
```
This will start both the database and the FastAPI server.

### Managing Data Volumes
By default, Docker Compose preserves your database in a named volume. 
- To shut down services: `docker compose down` (Your indexed documents are saved).
- To wipe everything and start fresh: `docker compose down -v` (This deletes the database volume).

---

## Production Deployment (Railway)

This repository is optimized for deployment on Railway (or similar platforms like Render / Fly.io).

### 1. Provision a PostgreSQL Database
- In your Railway project, add a **PostgreSQL** database.
- Ensure the database supports/enables the `pgvector` extension.

### 2. Deploy the Backend
- Connect your GitHub repository to Railway and deploy the backend directory.
- Railway will automatically detect the `Dockerfile` in `backend/Dockerfile` or use Nixpacks.

**Required Environment Variables for the Backend:**
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `ANTHROPIC_API_KEY` (or Google API key if configured)

### 3. Deploy the Frontend
- Deploy the `frontend/` directory as a separate Railway service.
- **Required Environment Variables for the Frontend:**
  - `BACKEND_API_URL`: Set this to the public URL of your deployed backend service (e.g., `https://riw-backend.up.railway.app`).

### Production Verification Checklist
After deployment, verify the system is stable:
1. **Health Check**: Ping `/health` on the backend.
2. **Ingestion**: Upload a small test PDF via the UI and confirm successful embedding.
3. **Local RAG**: Ask a question based exclusively on the uploaded PDF.
4. **Web Research**: Enable "Search the web" and ask a live question (e.g., "What is the news today?").
5. **Failure Handling**: Ask a highly specific fictional question with web search disabled, ensuring it gracefully returns an "Insufficient Evidence" response rather than crashing or hallucinating.

---

## Troubleshooting

### Symptom: `502 Bad Gateway / Upstream Timeout` during Web Research
**Cause**: Web research retrieves dozens of chunks. If embeddings are processed sequentially, the API request exceeds the proxy timeout (usually 30-60s).
**Fix**: Ensure your deployment includes the recent `SourceRanker` batching optimization. Do not artificially increase timeouts as a primary fix; the batched embedding resolves the CPU bottleneck.

### Symptom: LLM Synthesis Returns "Failed to generate structured synthesis"
**Cause**: The LLM produced malformed JSON or ran out of `max_tokens` budget.
**Fix**: The backend automatically attempts a bounded repair retry. If it consistently fails, check if `CLAUDE_MODEL` is set to an appropriate reasoning model (e.g., Claude 3.5 Sonnet) and ensure the `max_tokens` argument in `llm_service.py` is sufficiently large (4096+).

### Symptom: Frontend fails to fetch data from backend
**Cause**: The frontend cannot resolve the backend URL.
**Fix**: Ensure `BACKEND_API_URL` is set correctly in your production environment variables (do not include trailing slashes). Locally, Next.js proxies `/api/backend` to `http://127.0.0.1:8001` automatically.
