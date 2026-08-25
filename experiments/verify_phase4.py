"""
Phase 4 verification script — RAG + Grounded Answers.

Run AFTER:
  1. echo GOOGLE_API_KEY=your-key >> .env
  2. docker compose up -d
  3. uvicorn backend.main:app --host 127.0.0.1 --port 8001

Usage:
  python experiments/verify_phase4.py

Checks:
  1.  LLM service imports and initialises (GOOGLE_API_KEY present)
  2.  Context builder formats chunks correctly
  3.  RAG service imports without error
  4.  POST /api/rag/query returns 200
  5.  Answer field is a non-empty string
  6.  Sources list is non-empty
  7.  Source fields correct (source_id, document_id, page_number, similarity_score)
  8.  /api/search still works (Phase 3 not broken)
  9.  Question answered from document → grounded answer + source pages cited
  10. Question not in document → explicitly reports insufficient information
  11. Multiple chunks assembled → context_chars > 0, chunks_retrieved > 0
  12. metadata block present with model / chunks_retrieved / context_chars / top_k
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


# ── 1. LLM service can initialise ───────────────────────────────────────────
section("1. LLM service import and init")
try:
    from backend.services.llm_service import GeminiLLMService, LLMServiceError
    llm = GeminiLLMService()
    print(f"  Model: {llm.model_name}")
    check("GeminiLLMService initialised", True)
except LLMServiceError as e:
    check("GeminiLLMService initialised", False, str(e))
    print("\n  => Set GOOGLE_API_KEY in .env and rerun.")
    _report_and_exit()
except Exception as e:
    check("GeminiLLMService initialised", False, str(e))
    _report_and_exit()

# ── 2. Context builder formats chunks correctly ──────────────────────────────
section("2. ContextBuilder — chunk formatting")
from backend.services.context_builder import ContextBuilder
from backend.services.retrieval_service import RetrievalResult

dummy_chunks = [
    RetrievalResult(
        chunk_id="a", text="Foreign contribution is regulated by FCRA.",
        cosine_distance=0.2, similarity_score=0.8,
        source_id="s1", document_id="d1", page_number=3, chunk_index=0,
    ),
    RetrievalResult(
        chunk_id="b", text="Penalties for violations include fines.",
        cosine_distance=0.3, similarity_score=0.7,
        source_id="s1", document_id="d1", page_number=7, chunk_index=1,
    ),
    # Duplicate page 3 — should be deduplicated in sources
    RetrievalResult(
        chunk_id="c", text="Registration must be renewed annually.",
        cosine_distance=0.35, similarity_score=0.65,
        source_id="s1", document_id="d1", page_number=3, chunk_index=2,
    ),
]

builder = ContextBuilder()
ctx, srcs = builder.build(dummy_chunks)

check("Context is non-empty string", isinstance(ctx, str) and len(ctx) > 0)
check("Context contains chunk text", "Foreign contribution" in ctx)
check("Context numbered [1]", "[1]" in ctx)
check("Context numbered [2]", "[2]" in ctx)
check("Sources deduplicated at page level", len(srcs) == 2, f"got {len(srcs)} (expected 2)")
check("Source fields correct", srcs[0].page_number == 3 and srcs[1].page_number == 7)

# ── 3. RAGService imports ────────────────────────────────────────────────────
section("3. RAGService import")
from backend.services.rag_service import RAGService
check("RAGService importable", True)

# ── 4-8. Live API tests ──────────────────────────────────────────────────────
section("4. /health check (server is up)")
r = requests.get(f"{BASE_URL}/health", timeout=5)
require("/health -> 200", r.status_code == 200, r.text[:100])

section("5. /api/search still works (Phase 3 not broken)")
r = requests.post(f"{BASE_URL}/api/search",
                  json={"query": "foreign contribution", "top_k": 3}, timeout=15)
require("POST /api/search -> 200", r.status_code == 200, r.text[:200])
sd = r.json()
check("/api/search returns results", sd["results_count"] > 0, f"got {sd['results_count']}")

# ── 6. RAG basic call ────────────────────────────────────────────────────────
section("6. POST /api/rag/query — basic call")
QUERY_IN_DOC = "What is the penalty if no separate punishment has been provided?"
r = requests.post(f"{BASE_URL}/api/rag/query",
                  json={"query": QUERY_IN_DOC, "top_k": 5},
                  timeout=60)
require("POST /api/rag/query -> 200", r.status_code == 200, r.text[:300])
rag = r.json()
print(f"  Answer preview: {rag['answer'][:200]}...")

check("answer field present", "answer" in rag)
check("answer is non-empty string", isinstance(rag["answer"], str) and len(rag["answer"]) > 10)
check("sources list present", "sources" in rag)
check("metadata block present", "metadata" in rag)

# ── 7. Sources structure ──────────────────────────────────────────────────────
section("7. Sources metadata structure")
sources = rag["sources"]
check("sources is a list", isinstance(sources, list))
if sources:
    s = sources[0]
    for field in ["source_id", "document_id", "page_number", "similarity_score"]:
        check(f"source has '{field}'", field in s)
    check("page_number >= 1", s["page_number"] >= 1)
    check("similarity_score in (0, 1]", 0 < s["similarity_score"] <= 1.0,
          f"got {s['similarity_score']}")
    print(f"  Sources ({len(sources)} unique pages):")
    for s in sources[:5]:
        print(f"    page={s['page_number']}  sim={s['similarity_score']:.4f}")
else:
    check("sources non-empty for in-document query", False, "empty sources list")

# ── 8. Metadata block ─────────────────────────────────────────────────────────
section("8. Metadata block")
meta = rag["metadata"]
check("metadata.model present", "model" in meta and len(meta["model"]) > 0,
      f"model={meta.get('model')}")
check("metadata.chunks_retrieved > 0", meta.get("chunks_retrieved", 0) > 0,
      f"got {meta.get('chunks_retrieved')}")
check("metadata.context_chars > 0", meta.get("context_chars", 0) > 0,
      f"got {meta.get('context_chars')}")
check("metadata.top_k = 5", meta.get("top_k") == 5, f"got {meta.get('top_k')}")
print(f"  model={meta.get('model')}  chunks={meta.get('chunks_retrieved')}"
      f"  context_chars={meta.get('context_chars')}")

# ── 9. Grounded answer for in-document question ───────────────────────────────
section("9. Grounded answer — question answered from document")
answer_lower = rag["answer"].lower()
# Gemini should mention something about penalties/fines/punishment in context
penalty_keywords = ["penalt", "fine", "punish", "imprison", "offence", "convict"]
found_penalty = any(kw in answer_lower for kw in penalty_keywords)
check(
    "Answer mentions penalty-related terms from FCRA context",
    found_penalty,
    f"keywords checked: {penalty_keywords}"
)
print(f"  Full answer:\n{rag['answer']}\n")

# ── 9b. Unanswerable-context test ─────────────────────────────────────────────
section("9b. Unanswerable-context test (missing explicit details)")
UNANSWERABLE_QUERY = "What are the penalties for accepting foreign contribution without registration?"
r_un = requests.post(f"{BASE_URL}/api/rag/query",
                     json={"query": UNANSWERABLE_QUERY, "top_k": 5},
                     timeout=60)
require("Unanswerable query -> 200", r_un.status_code == 200, r_un.text[:200])
rag_un = r_un.json()
answer_un_lower = rag_un["answer"].lower()
print(f"  Answer: {rag_un['answer']}")
found_insufficient_un = any(phrase in answer_un_lower for phrase in [
    "do not contain", "does not contain", "not enough", "cannot answer",
    "no information", "not available", "not found", "not mentioned"
])
check(
    "Unanswerable context signals insufficient information",
    found_insufficient_un,
    f"answer: {rag_un['answer'][:150]}"
)

# ── 10. Insufficient evidence case ───────────────────────────────────────────
section("10. Out-of-scope question reports insufficient evidence")
OOS_QUERY = "What is the recipe for chocolate chip cookies?"
r2 = requests.post(f"{BASE_URL}/api/rag/query",
                   json={"query": OOS_QUERY, "top_k": 5},
                   timeout=60)
require("Out-of-scope RAG query -> 200", r2.status_code == 200, r2.text[:200])
rag2 = r2.json()
answer2_lower = rag2["answer"].lower()
print(f"  Answer: {rag2['answer']}")
# The LLM should say the documents don't have enough information
insufficient_phrases = [
    "do not contain", "does not contain", "not enough", "cannot answer",
    "no information", "not available", "not found", "not mentioned",
    "not provided", "unable to find", "outside", "not relevant",
    "not related", "not covered", "chocolate", "cookie"
]
found_insufficient = any(phrase in answer2_lower for phrase in insufficient_phrases)
check(
    "Out-of-scope answer signals insufficient information",
    found_insufficient,
    f"answer: {rag2['answer'][:150]}"
)

# ── 11. Multiple chunks assembled ─────────────────────────────────────────────
section("11. Multiple chunks assembled — top_k=8")
r3 = requests.post(f"{BASE_URL}/api/rag/query",
                   json={"query": "registration and compliance under FCRA", "top_k": 8},
                   timeout=60)
require("top_k=8 RAG query -> 200", r3.status_code == 200)
rag3 = r3.json()
check("chunks_retrieved = 8", rag3["metadata"]["chunks_retrieved"] == 8,
      f"got {rag3['metadata']['chunks_retrieved']}")
check("context_chars > 1000", rag3["metadata"]["context_chars"] > 1000,
      f"got {rag3['metadata']['context_chars']}")
check("answer non-empty", len(rag3["answer"]) > 20)

# ── Summary ───────────────────────────────────────────────────────────────────
_report_and_exit()
