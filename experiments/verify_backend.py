"""
Comprehensive Backend Verification Script.
Verifies all 16 pipeline requirements against a running FastAPI server.
"""

import sys
import os
import requests
import time
import json

sys.path.insert(0, ".")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BASE_URL = "http://127.0.0.1:8001"

PASS = "[PASS]"
FAIL = "[FAIL]"
_failures = []


def section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check(label, condition, detail=""):
    suffix = f" -- {detail}" if detail else ""
    if condition:
        print(f"  {PASS}  {label}{suffix}")
    else:
        print(f"  {FAIL}  {label}{suffix}")
        _failures.append(label)


def require(label, condition, detail=""):
    check(label, condition, detail)
    if not condition:
        print(f"\n  FATAL: '{label}' failed. Cannot continue.\n")
        _report_and_exit()


def _report_and_exit():
    print("\n" + "=" * 60)
    if _failures:
        print(f"  FAILED: {len(_failures)} check(s):")
        for f in _failures:
            print(f"    - {f}")
    else:
        print("  All checks passed [OK]")
    print("=" * 60 + "\n")
    sys.exit(1 if _failures else 0)


def call_api_with_retry(method, url, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if method == "get":
                r = requests.get(url, **kwargs)
            else:
                r = requests.post(url, **kwargs)
            
            # 502 or 429 usually means Gemini rate limit from our backend
            if r.status_code in [502, 429] and attempt < max_retries - 1:
                print(f"  (Hit rate limit {r.status_code}, sleeping 65s before retry...)")
                time.sleep(65)
                continue
            return r
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"  (Request exception {e}, sleeping 5s...)")
                time.sleep(5)
                continue
            raise


# ── 1. Health ─────────────────────────────────────────────────────────────────
section("1. Health Endpoint")
r = requests.get(f"{BASE_URL}/health", timeout=5)
require("/health -> 200", r.status_code == 200, r.text[:100])

# ── 2 & 4 & 5. PDF Ingestion ──────────────────────────────────────────────────
section("2. PDF Ingestion")
pdf_path = "data/raw/test.pdf"
if not os.path.exists(pdf_path):
    print(f"WARNING: {pdf_path} not found. Skipping PDF ingestion test.")
else:
    with open(pdf_path, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        r_pdf = requests.post(f"{BASE_URL}/api/sources/pdf", files=files, timeout=60)
    require("POST /api/sources/pdf -> 200", r_pdf.status_code == 200, r_pdf.text[:100])
    pdf_res = r_pdf.json()
    check("Persisted Source ID returned", "id" in pdf_res.get("source", {}))
    check("Chunks generated", pdf_res.get("stats", {}).get("chunks_embedded", 0) > 0)


# ── 3 & 4. URL Ingestion ──────────────────────────────────────────────────────
section("3. URL Ingestion")
url_data = {"url": "https://example.com"}
r_url = requests.post(f"{BASE_URL}/api/sources/url", json=url_data, timeout=60)
require("POST /api/sources/url -> 200", r_url.status_code == 200, r_url.text[:100])
url_res = r_url.json()
check("Persisted Source ID returned (URL)", "id" in url_res.get("source", {}))
check("Chunks generated (URL)", url_res.get("stats", {}).get("chunks_embedded", 0) > 0)


# ── 6 & 7. Semantic Search ────────────────────────────────────────────────────
section("7. Semantic /api/search")
r_search = requests.post(f"{BASE_URL}/api/search", json={"query": "penalty", "top_k": 3}, timeout=30)
require("POST /api/search -> 200", r_search.status_code == 200)
search_res = r_search.json()
check("Search returns results", len(search_res.get("results", [])) > 0)
if len(search_res.get("results", [])) > 0:
    first_res = search_res["results"][0]
    check("Result has text", "text" in first_res)
    check("Result has similarity score", "similarity_score" in first_res)
    check("Result has document_id", "document_id" in first_res)
    check("Result has page_number", "page_number" in first_res)

print("\n--- Manual Inspection 1: /api/search Output ---")
print(search_res.get("results", [])[0] if search_res.get("results") else "No results")
print("-----------------------------------------------")


# ── 8 & 9. Answerable RAG ─────────────────────────────────────────────────────
section("8 & 9. Answerable RAG")
QUERY_IN_DOC = "What is the penalty if no separate punishment has been provided?"
r_rag = call_api_with_retry("post", f"{BASE_URL}/api/rag/query", json={"query": QUERY_IN_DOC}, timeout=60)
require("POST /api/rag/query -> 200", r_rag.status_code == 200, r_rag.text[:100])
rag_res = r_rag.json()
check("RAG has answer", len(rag_res.get("answer", "")) > 10)
check("RAG has sources", len(rag_res.get("sources", [])) > 0)

print("\n--- Manual Inspection 2: Answerable RAG Output ---")
print(f"Answer: {rag_res.get('answer')}")
print(f"Sources: {rag_res.get('sources')}")
print("--------------------------------------------------")


# ── 10. Unanswerable RAG ──────────────────────────────────────────────────────
section("10. Unanswerable RAG")
r_rag_oos = call_api_with_retry("post", f"{BASE_URL}/api/rag/query", json={"query": "How to make a cake?"}, timeout=60)
require("POST /api/rag/query (OOS) -> 200", r_rag_oos.status_code == 200)
rag_oos_res = r_rag_oos.json()
check("Insufficient evidence reported", "not contain enough information" in rag_oos_res.get("answer", "").lower() or "insufficient" in rag_oos_res.get("answer", "").lower())


# ── 11 & 12. Local-only Research ──────────────────────────────────────────────
section("11 & 12. Local-only Research")
r_res_local = call_api_with_retry("post", f"{BASE_URL}/api/research/query", json={"query": QUERY_IN_DOC, "web_search": False}, timeout=120)
require("Local Research -> 200", r_res_local.status_code == 200)
res_local = r_res_local.json()
check("Sub-questions generated", len(res_local.get("sub_questions", [])) > 0)
check("Findings populated", len(res_local.get("findings", [])) > 0)
has_web = any(s.get("source_id") == "web" for s in res_local.get("sources", []))
check("No web sources present", not has_web)


# ── 13 & 14. Web-enabled Research ─────────────────────────────────────────────
section("13 & 14. Web-enabled Research")
r_res_web = call_api_with_retry("post", f"{BASE_URL}/api/research/query", json={"query": "What is the latest stable version of Python?", "web_search": True}, timeout=180)
require("Web Research -> 200", r_res_web.status_code == 200)
res_web = r_res_web.json()
has_web = any(s.get("source_id") == "web" for s in res_web.get("sources", []))
check("Web sources extracted & ranked", has_web)

print("\n--- Manual Inspection 3: Web-enabled Research Output ---")
print(f"Original Query: {res_web.get('original_query')}")
print(f"Overall Summary: {res_web.get('overall_summary')}")
print(f"Sources: {[s.get('document_id') for s in res_web.get('sources', []) if s.get('source_id') == 'web']}")
print("--------------------------------------------------------")


# ── 15. Web Failure Graceful Degradation ──────────────────────────────────────
section("15. Web Failure Graceful Degradation")
# Using a query that returns no valid web results
r_res_fail = call_api_with_retry("post", f"{BASE_URL}/api/research/query", json={"query": "934857398457xyznonexistent", "web_search": True}, timeout=120)
require("Web Failure -> 200 (Graceful degradation)", r_res_fail.status_code == 200)
res_fail = r_res_fail.json()
check("Falls back correctly when web fails", "insufficient_evidence" in str(res_fail) or len(res_fail.get("findings", [])) > 0)


# ── 16. Invalid/Malformed API Requests ────────────────────────────────────────
section("16. Invalid/Malformed API Requests")
r_inv = requests.post(f"{BASE_URL}/api/rag/query", json={"top_k": 5}, timeout=10) # missing 'query'
check("Missing required field -> 422", r_inv.status_code == 422)

r_inv2 = requests.post(f"{BASE_URL}/api/rag/query", json={"query": ""}, timeout=10) # empty string
check("Empty string -> 422 or 400", r_inv2.status_code in [400, 422])

_report_and_exit()
