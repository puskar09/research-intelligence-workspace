"""
Phase 6 verification script — Web Research + Source Intelligence.

Run AFTER:
  uvicorn backend.main:app --host 127.0.0.1 --port 8001

Usage:
  python experiments/verify_phase6.py
"""

import sys
import os
import requests

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


# ── 1. Existing Endpoints Check ──────────────────────────────────────────────
section("1. Existing Endpoints Check")

r = requests.get(f"{BASE_URL}/health", timeout=5)
require("/health -> 200", r.status_code == 200, r.text[:100])

r = requests.post(f"{BASE_URL}/api/search", json={"query": "test", "top_k": 1}, timeout=15)
require("POST /api/search -> 200", r.status_code == 200)

r = requests.post(f"{BASE_URL}/api/rag/query", json={"query": "What is FCRA?", "top_k": 1}, timeout=60)
require("POST /api/rag/query -> 200", r.status_code == 200)


# ── 2. Local-only Research Query ─────────────────────────────────────────────
section("2. POST /api/research/query — Local Only")
QUERY_IN_DOC = "What is the penalty if no separate punishment has been provided?"
r = requests.post(f"{BASE_URL}/api/research/query",
                  json={"query": QUERY_IN_DOC, "web_search": False},
                  timeout=120)
require("Local Research -> 200", r.status_code == 200, r.text[:300])
res = r.json()

print(f"  Original Query: {res['original_query']}")
check("sub_questions generated", len(res["sub_questions"]) >= 1)
check("findings list populated", len(res["findings"]) > 0)
check("overall_summary is non-empty", len(res["overall_summary"]) > 10)

has_web_sources = any(s["source_id"] == "web" for s in res.get("sources", []))
check("No web sources in local-only search", not has_web_sources)


# ── 3. Web-enabled Research Query ────────────────────────────────────────────
section("3. POST /api/research/query — Web Enabled")
WEB_QUERY = "What is the latest stable version of the Python programming language?"
r_web = requests.post(f"{BASE_URL}/api/research/query",
                      json={"query": WEB_QUERY, "web_search": True},
                      timeout=180)

require("Web Research -> 200", r_web.status_code == 200, r_web.text[:300])
res_web = r_web.json()

print(f"  Original Query: {res_web['original_query']}")
check("sub_questions generated", len(res_web["sub_questions"]) >= 1)
check("findings list populated", len(res_web["findings"]) > 0)

has_web_sources = any(s["source_id"] == "web" for s in res_web.get("sources", []))
check("Web sources are present in results", has_web_sources)
if has_web_sources:
    web_sources = [s for s in res_web["sources"] if s["source_id"] == "web"]
    print(f"  Found {len(web_sources)} web sources (URLs: {[s['document_id'][:50] for s in web_sources]})")

# ── Summary ───────────────────────────────────────────────────────────────────
_report_and_exit()
