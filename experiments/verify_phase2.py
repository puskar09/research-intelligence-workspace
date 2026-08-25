"""
Phase 2 verification script.

Run this AFTER:
  1. docker compose up -d
  2. uvicorn backend.main:app --reload --port 8001

Usage:
  python experiments/verify_phase2.py

Checks:
  1. /health
  2. PDF ingestion (data/raw/test.pdf)
  3. URL ingestion (https://example.com)
  4. Queries the database directly to confirm records exist
  5. Verifies pgvector extension is enabled
"""

import sys
import requests
import psycopg2
from pathlib import Path

BASE_URL = "http://127.0.0.1:8001"

DB_PARAMS = {
    "dbname": "riw",
    "user": "riw_user",
    "password": "riw_password",
    "host": "localhost",
    "port": 5432,
}


def section(title: str) -> None:
    print(f"\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "[PASS]" if condition else "[FAIL]"
    suffix = f" -- {detail}" if detail else ""
    print(f"  {status}  {label}{suffix}")
    if not condition:
        sys.exit(1)


# ── 1. Health ──────────────────────────────────────────────────────────────
section("1. Health check")
r = requests.get(f"{BASE_URL}/health")
check("/health returns 200", r.status_code == 200)
check("/health body", r.json() == {"status": "ok"})

# ── 2. PDF ingestion ────────────────────────────────────────────────────────
section("2. PDF ingestion")
pdf_path = Path("data/raw/test.pdf")
check("test.pdf exists", pdf_path.exists())

with open(pdf_path, "rb") as f:
    r = requests.post(
        f"{BASE_URL}/api/sources/pdf",
        files={"file": ("test.pdf", f, "application/pdf")},
    )
check("POST /api/sources/pdf -> 200", r.status_code == 200, r.text[:200])
pdf_data = r.json()
pdf_source_id = pdf_data["source"]["id"]
check("source.url is null (PDF upload)", pdf_data["source"]["url"] is None)
check("source.source_type = pdf", pdf_data["source"]["source_type"] == "pdf")
check("document.total_pages > 0", pdf_data["document"]["total_pages"] > 0)
check("chunks > 0", pdf_data["stats"]["total_chunks"] > 0)
print(f"  Pages: {pdf_data['document']['total_pages']}, Chunks: {pdf_data['stats']['total_chunks']}")

# ── 3. URL ingestion ────────────────────────────────────────────────────────
section("3. URL ingestion")
r = requests.post(
    f"{BASE_URL}/api/sources/url",
    json={"url": "https://example.com"},
)
check("POST /api/sources/url -> 200", r.status_code == 200, r.text[:200])
url_data = r.json()
url_source_id = url_data["source"]["id"]
check("source.url = https://example.com", url_data["source"]["url"] == "https://example.com")
check("source.title set", bool(url_data["source"]["title"]))
check("chunks > 0", url_data["stats"]["total_chunks"] > 0)
print(f"  Title: {url_data['source']['title']}, Chunks: {url_data['stats']['total_chunks']}")

# ── 4. Database verification ────────────────────────────────────────────────
section("4. Database records")
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor()

# pgvector extension
cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
row = cur.fetchone()
check("pgvector extension enabled", row is not None)

# Sources
cur.execute("SELECT COUNT(*) FROM sources WHERE id = %s", (pdf_source_id,))
check("PDF source in DB", cur.fetchone()[0] == 1)

cur.execute("SELECT COUNT(*) FROM sources WHERE id = %s", (url_source_id,))
check("URL source in DB", cur.fetchone()[0] == 1)

# Documents
cur.execute("SELECT COUNT(*) FROM documents WHERE source_id = %s", (pdf_source_id,))
check("PDF document in DB", cur.fetchone()[0] == 1)

cur.execute("SELECT COUNT(*) FROM documents WHERE source_id = %s", (url_source_id,))
check("URL document in DB", cur.fetchone()[0] == 1)

# Pages
cur.execute("""
    SELECT COUNT(*) FROM pages p
    JOIN documents d ON p.document_id = d.id
    WHERE d.source_id = %s
""", (pdf_source_id,))
pdf_page_count = cur.fetchone()[0]
check("PDF pages in DB", pdf_page_count > 0, f"{pdf_page_count} rows")

# Chunks
cur.execute("SELECT COUNT(*) FROM chunks WHERE source_id = %s", (pdf_source_id,))
pdf_chunk_count = cur.fetchone()[0]
check("PDF chunks in DB", pdf_chunk_count > 0, f"{pdf_chunk_count} rows")

cur.execute("SELECT COUNT(*) FROM chunks WHERE source_id = %s", (url_source_id,))
url_chunk_count = cur.fetchone()[0]
check("URL chunks in DB", url_chunk_count > 0, f"{url_chunk_count} rows")

# Spot check: every chunk has a valid page_number
cur.execute("SELECT COUNT(*) FROM chunks WHERE page_number IS NULL OR page_number < 1")
check("No chunks with null/invalid page_number", cur.fetchone()[0] == 0)

cur.close()
conn.close()

# ── 5. Summary ──────────────────────────────────────────────────────────────
section("All checks passed [OK]")
print(f"  PDF  source_id: {pdf_source_id}")
print(f"  URL  source_id: {url_source_id}")
print(f"  PDF  pages={pdf_page_count}  chunks={pdf_chunk_count}")
print(f"  URL  chunks={url_chunk_count}")
print()
