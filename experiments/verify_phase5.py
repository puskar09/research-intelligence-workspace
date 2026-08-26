"""
Phase 5 verification script — Research Intelligence.

Run AFTER:
  uvicorn backend.main:app --host 127.0.0.1 --port 8001

Usage:
  python experiments/verify_phase5.py
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

# ── 2. Research Query — Answerable ───────────────────────────────────────────
section("2. POST /api/research/query — Answerable query")
QUERY_IN_DOC = "What is the penalty if no separate punishment has been provided?"
r = requests.post(f"{BASE_URL}/api/research/query",
                  json={"query": QUERY_IN_DOC},
                  timeout=120)
require("POST /api/research/query -> 200", r.status_code == 200, r.text[:300])
res = r.json()

print(f"  Original Query: {res['original_query']}")
print(f"  Sub-questions generated: {len(res['sub_questions'])}")

check("sub_questions list populated", len(res["sub_questions"]) >= 1)
check("findings list populated", len(res["findings"]) > 0)
check("overall_summary is non-empty", len(res["overall_summary"]) > 10)
check("sources list is present", "sources" in res and len(res["sources"]) > 0)

# Check findings schema
valid_findings = True
found_evidence = False
for f in res["findings"]:
    if not isinstance(f.get("sub_question"), str) or not isinstance(f.get("evidence"), str):
        valid_findings = False
    if not f.get("insufficient_evidence", True):
        found_evidence = True

check("findings follow schema", valid_findings)
check("at least one finding has sufficient evidence", found_evidence)


# ── 3. Research Query — Unsupported ───────────────────────────────────────────
section("3. POST /api/research/query — Unsupported query")
OOS_QUERY = "What is the recipe for chocolate chip cookies?"
r_oos = requests.post(f"{BASE_URL}/api/research/query",
                      json={"query": OOS_QUERY},
                      timeout=120)
require("OOS Research query -> 200", r_oos.status_code == 200, r_oos.text[:200])
res_oos = r_oos.json()

print(f"  Original Query: {res_oos['original_query']}")

all_insufficient = all(f.get("insufficient_evidence", False) for f in res_oos["findings"])
check("All findings marked insufficient_evidence=true", all_insufficient)

summary_lower = res_oos["overall_summary"].lower()
insufficient_phrases = [
    "do not contain", "does not contain", "not enough", "cannot answer",
    "no information", "not available", "not found", "not mentioned",
    "not provided", "unable to find", "outside", "not relevant"
]
found_insufficient = any(phrase in summary_lower for phrase in insufficient_phrases)
check("Overall summary signals insufficient information", found_insufficient, f"Summary: {res_oos['overall_summary'][:100]}")

# ── Summary ───────────────────────────────────────────────────────────────────
_report_and_exit()
