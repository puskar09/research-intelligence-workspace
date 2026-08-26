"""
System Validation — deterministic, no LLM calls.

Sections:
  A. Local retrieval (against live DB)
  B. Web search pipeline (live network, no LLM)
  C. Local + Web merging via SourceRanker (mock + live)
  D. Discovery service with mock LLM
  E. ContextBuilder source contract verification
  F. API schema & import check
  G. ResearchService grounding prompt inspection
  H. Frontend type contract inspection (static)

Run from workspace root:
  python experiments/validate_system.py
"""

import sys, os, json, re, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
INFO = "\033[94mINFO\033[0m"

results = {}

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(label, detail=""):
    results[label] = "PASS"
    print(f"  [{PASS}] {label}" + (f" — {detail}" if detail else ""))

def fail(label, detail=""):
    results[label] = "FAIL"
    print(f"  [{FAIL}] {label}" + (f" — {detail}" if detail else ""))

def warn(label, detail=""):
    results[label] = "WARN"
    print(f"  [{WARN}] {label}" + (f" — {detail}" if detail else ""))

def info(msg):
    print(f"  [{INFO}] {msg}")


# =============================================================================
# A. LOCAL RETRIEVAL
# =============================================================================
section("A. LOCAL RETRIEVAL")

try:
    from backend.db.database import SessionLocal
    from backend.services.retrieval_service import RetrievalService
    db = SessionLocal()
    svc = RetrievalService()
    results_chunks = svc.search(db=db, query="FCRA foreign contribution registration", top_k=3)
    
    if not results_chunks:
        warn("A1-retrieval-returns-chunks", "No chunks returned — DB may be empty or embeddings missing")
    else:
        ok("A1-retrieval-returns-chunks", f"{len(results_chunks)} chunks returned")
        c = results_chunks[0]
        if c.chunk_id and c.text and c.source_id and c.document_id:
            ok("A2-chunk-fields-present", f"chunk_id={c.chunk_id[:8]}... page={c.page_number}")
        else:
            fail("A2-chunk-fields-present", "Missing one or more required fields")
        if c.similarity_score > 0:
            ok("A3-similarity-score-nonzero", f"score={c.similarity_score:.4f}")
        else:
            warn("A3-similarity-score-nonzero", f"score={c.similarity_score}")
        if c.text and len(c.text) > 20:
            ok("A4-chunk-text-preserved", f"text length={len(c.text)} chars")
        else:
            fail("A4-chunk-text-preserved", "Chunk text empty or too short")
        seen = set()
        dupes = 0
        for ch in results_chunks:
            if ch.chunk_id in seen:
                dupes += 1
            seen.add(ch.chunk_id)
        if dupes == 0:
            ok("A5-no-duplicate-chunks")
        else:
            warn("A5-no-duplicate-chunks", f"{dupes} duplicates")
    db.close()
except Exception as e:
    fail("A-local-retrieval", str(e))


# =============================================================================
# B. WEB SEARCH PIPELINE
# =============================================================================
section("B. WEB SEARCH PIPELINE")

web_chunks_available = []
try:
    from backend.services.web_research_service import WebResearchService, DDGLiteSearchProvider, WebChunk

    provider = DDGLiteSearchProvider()
    test_query = "FCRA Act India foreign contribution regulation"
    
    try:
        urls = provider.search(test_query, max_results=2)
        if urls and any(u.startswith("http") for u in urls):
            ok("B1-ddg-returns-urls", f"Got {len(urls)} URL(s): {urls[0][:60]}")
        else:
            warn("B1-ddg-returns-urls", f"Got {len(urls)} URLs — may be anti-bot or network issue")
    except Exception as e:
        fail("B1-ddg-returns-urls", str(e))

    web_svc = WebResearchService()
    try:
        chunks = web_svc.get_web_chunks(query=test_query, max_urls=1)
        if chunks:
            web_chunks_available = chunks
            ok("B2-web-chunks-returned", f"{len(chunks)} chunks from web")
            wc = chunks[0]
            if wc.chunk_id and wc.text and wc.url:
                ok("B3-webchunk-fields", f"url={wc.url[:50]}...")
            else:
                fail("B3-webchunk-fields", "Missing chunk_id/text/url")
            if len(wc.text) > 100:
                ok("B4-webchunk-text-is-content", f"text length={len(wc.text)}")
            else:
                warn("B4-webchunk-text-is-content", f"text length only {len(wc.text)}")
            if wc.url.startswith("http"):
                ok("B5-webchunk-url-preserved", wc.url[:60])
            else:
                fail("B5-webchunk-url-preserved", f"URL={wc.url}")
        else:
            warn("B2-web-chunks-returned", "0 chunks returned — fetch may have failed")
    except Exception as e:
        fail("B2-web-chunks-returned", str(e))

except Exception as e:
    fail("B-web-pipeline-import", str(e))


# =============================================================================
# C. SOURCE RANKER — local + web merging
# =============================================================================
section("C. LOCAL + WEB MERGING (SourceRanker)")

try:
    from backend.services.source_ranker import SourceRanker
    from backend.services.retrieval_service import RetrievalResult
    from backend.services.web_research_service import WebChunk

    ranker = SourceRanker()
    local_mock = [
        RetrievalResult(chunk_id="local-1", text="The FCRA requires every organization to open an FCRA account at SBI.",
                        cosine_distance=0.15, similarity_score=0.85, source_id="src-pdf-1",
                        document_id="doc-pdf-1", page_number=14, chunk_index=0),
        RetrievalResult(chunk_id="local-2", text="Foreign contributions above 10 lakh must be reported within 30 days.",
                        cosine_distance=0.20, similarity_score=0.80, source_id="src-pdf-2",
                        document_id="doc-pdf-2", page_number=22, chunk_index=1),
    ]
    web_mock = [
        WebChunk(chunk_id="web-1", text="NGOs registered under FCRA must file annual returns with the Ministry of Home Affairs.",
                 url="https://mha.gov.in/fcra", chunk_index=0),
        WebChunk(chunk_id="web-2", text="The Supreme Court upheld the mandatory SBI branch rule in 2021.",
                 url="https://indiankanoon.org/fcra", chunk_index=1),
    ]

    ranked = ranker.rank(query="FCRA registration requirements", local_results=local_mock, web_chunks=web_mock, top_k=3)

    if len(ranked) == 3:
        ok("C1-ranker-returns-top-k", f"{len(ranked)} results")
    else:
        warn("C1-ranker-returns-top-k", f"Expected 3, got {len(ranked)}")

    web_ranked = [r for r in ranked if r.source_id == "web"]
    if web_ranked:
        ok("C2-web-chunks-in-ranked-output", f"{len(web_ranked)} web chunk(s)")
        if web_ranked[0].document_id.startswith("http"):
            ok("C3-web-url-in-document-id", web_ranked[0].document_id[:50])
        else:
            fail("C3-web-url-in-document-id", f"document_id={web_ranked[0].document_id}")
    else:
        warn("C2-web-chunks-in-ranked-output", "No web chunks in top-k — local may dominate by score")

    distances = [r.cosine_distance for r in ranked]
    if distances == sorted(distances):
        ok("C4-ranking-sorted-by-distance")
    else:
        fail("C4-ranking-sorted-by-distance", f"distances={distances}")

    text_ok = all(r.text for r in ranked)
    if text_ok:
        ok("C5-text-preserved-through-ranking")
    else:
        fail("C5-text-preserved-through-ranking", "Some chunks missing text after ranking")

except Exception as e:
    fail("C-source-ranker", str(e))


# =============================================================================
# D. DISCOVERY SERVICE — mock LLM
# =============================================================================
section("D. RESEARCH DISCOVERY (Mock LLM)")

try:
    from backend.services.llm_service import BaseLLMService
    from backend.services.research_discovery import ResearchDiscoveryService

    MOCK_RESPONSE = json.dumps({
        "topic": "FCRA Act",
        "questions": [
            {"id": "q1", "question": "What are FCRA registration requirements for NGOs?", "category": "Legal"},
            {"id": "q2", "question": "How are foreign contributions taxed under FCRA?", "category": "Financial"},
            {"id": "q3", "question": "What penalties exist for FCRA violations?", "category": "Compliance"},
            {"id": "q4", "question": "Which organizations are exempt from FCRA?", "category": "Exemptions"},
            {"id": "q5", "question": "How does FCRA interact with FDI regulations?", "category": "Policy"},
        ]
    })

    class MockLLM(BaseLLMService):
        model_name = "mock"
        def generate(self, prompt: str) -> str:
            return MOCK_RESPONSE

    class MockRetrieval:
        def search(self, db, query, top_k):
            return []

    svc = ResearchDiscoveryService(llm_service=MockLLM(), retrieval_service=MockRetrieval())
    result = svc.discover(db=None, topic="FCRA Act", web_search=False)

    if result.get("topic") == "FCRA Act":
        ok("D1-discovery-topic-preserved")
    else:
        fail("D1-discovery-topic-preserved", str(result))

    qs = result.get("questions", [])
    if len(qs) == 5:
        ok("D2-discovery-5-questions", f"got {len(qs)}")
    else:
        fail("D2-discovery-5-questions", f"got {len(qs)}")

    schema_ok = all("id" in q and "question" in q and "category" in q for q in qs)
    if schema_ok:
        ok("D3-discovery-question-schema")
    else:
        fail("D3-discovery-question-schema", "Missing id/question/category in some question")

    # Caching test
    call_count = [0]
    class CountingLLM(BaseLLMService):
        model_name = "mock"
        def generate(self, prompt: str) -> str:
            call_count[0] += 1
            return MOCK_RESPONSE

    svc2 = ResearchDiscoveryService(llm_service=CountingLLM(), retrieval_service=MockRetrieval())
    svc2.discover(db=None, topic="cache test", web_search=False)
    svc2.discover(db=None, topic="cache test", web_search=False)
    if call_count[0] == 1:
        ok("D4-discovery-caching", "2nd call served from cache")
    else:
        warn("D4-discovery-caching", f"LLM called {call_count[0]} times for same topic")

    svc2.discover(db=None, topic="different topic", web_search=False)
    if call_count[0] == 2:
        ok("D5-cache-miss-on-new-topic")
    else:
        warn("D5-cache-miss-on-new-topic", f"call_count={call_count[0]}")

except Exception as e:
    fail("D-discovery", str(e))


# =============================================================================
# E. CONTEXT BUILDER SOURCE CONTRACT
# =============================================================================
section("E. CONTEXT BUILDER — SOURCE CONTRACT")

try:
    from backend.services.context_builder import ContextBuilder
    from backend.services.retrieval_service import RetrievalResult

    cb = ContextBuilder()
    local_chunks = [
        RetrievalResult(chunk_id="c1", text="The FCRA requires SBI account.", cosine_distance=0.1,
                       similarity_score=0.9, source_id="src-1", document_id="doc-1", page_number=5, chunk_index=0),
        RetrievalResult(chunk_id="c2", text="Foreign contributions must be reported.", cosine_distance=0.2,
                       similarity_score=0.8, source_id="web", document_id="https://mha.gov.in/fcra",
                       page_number=1, chunk_index=0),
    ]
    ctx, sources = cb.build(local_chunks)

    if "SBI account" in ctx and "Foreign contributions" in ctx:
        ok("E1-context-text-contains-chunks")
    else:
        fail("E1-context-text-contains-chunks")

    if sources[0].text == "The FCRA requires SBI account.":
        ok("E2-sourceref-carries-text")
    else:
        fail("E2-sourceref-carries-text", f"got: {sources[0].text}")

    if sources[0].source_type == "pdf":
        ok("E3-pdf-sourcetype-set")
    else:
        fail("E3-pdf-sourcetype-set", f"source_type={sources[0].source_type}")

    if sources[0].url is None:
        ok("E4-pdf-url-is-none")
    else:
        fail("E4-pdf-url-is-none", f"url={sources[0].url}")

    if sources[1].source_type == "web":
        ok("E5-web-sourcetype-set")
    else:
        fail("E5-web-sourcetype-set", f"source_type={sources[1].source_type}")

    if sources[1].url == "https://mha.gov.in/fcra":
        ok("E6-web-url-preserved")
    else:
        fail("E6-web-url-preserved", f"url={sources[1].url}")

    required = ["chunk_id","source_id","document_id","page_number","similarity_score","text","source_type","url"]
    missing_fields = [f for f in required if not hasattr(sources[0], f)]
    if not missing_fields:
        ok("E7-all-sourceref-fields-present")
    else:
        fail("E7-all-sourceref-fields-present", f"Missing: {missing_fields}")

except Exception as e:
    fail("E-context-builder", str(e))


# =============================================================================
# F. API SCHEMA & IMPORT CHECK
# =============================================================================
section("F. API SCHEMA & IMPORT CHECK")

try:
    from backend.api.research import (
        SourceRef, ResearchQueryResponse, ResearchQueryRequest,
        ResearchDiscoveryRequest, ResearchDiscoveryResponse, FindingModel, ResearchMetadata
    )
    ok("F1-research-api-imports")

    sr = SourceRef(chunk_id="c1", source_id="s1", document_id="d1", page_number=5, similarity_score=0.85,
                   text="Evidence.", source_type="pdf", url=None)
    assert sr.text == "Evidence." and sr.source_type == "pdf" and sr.url is None
    ok("F2-sourceref-optional-fields-work")

    sr_web = SourceRef(chunk_id="c2", source_id="web", document_id="https://mha.gov.in", page_number=1,
                       similarity_score=0.75, text="Web evidence.", source_type="web", url="https://mha.gov.in")
    assert sr_web.source_type == "web" and sr_web.url == "https://mha.gov.in"
    ok("F3-web-sourceref-works")

    sr_null = SourceRef(chunk_id="c3", source_id="s3", document_id="d3", page_number=1, similarity_score=0.5)
    assert sr_null.text is None and sr_null.source_type is None
    ok("F4-backward-compatible-null-fields")

    from backend.api.rag import RAGQueryResponse, SourceRef as RagSourceRef, RAGQueryRequest
    ok("F5-rag-api-imports")

    from backend.api.sources import router as sources_router
    from backend.api.search import router as search_router
    ok("F6-all-routers-import")

except Exception as e:
    fail("F-api-imports", str(e))


# =============================================================================
# G. GROUNDING PROMPT INSPECTION
# =============================================================================
section("G. GROUNDING PROMPT INSPECTION")

try:
    from backend.services.research_service import _SYNTHESIS_PROMPT, _SUB_QUESTIONS_PROMPT, _extract_json

    if "ONLY" in _SYNTHESIS_PROMPT:
        ok("G1-synthesis-has-grounding-rule")
    else:
        fail("G1-synthesis-has-grounding-rule")

    if "insufficient_evidence" in _SYNTHESIS_PROMPT:
        ok("G2-synthesis-has-insufficient-evidence-flag")
    else:
        fail("G2-synthesis-has-insufficient-evidence-flag")

    if "[1]" in _SYNTHESIS_PROMPT or "square brackets" in _SYNTHESIS_PROMPT:
        ok("G3-synthesis-has-citation-instructions")
    else:
        fail("G3-synthesis-has-citation-instructions")

    if "{context}" in _SYNTHESIS_PROMPT and "{question}" in _SYNTHESIS_PROMPT:
        ok("G4-synthesis-has-template-vars")
    else:
        fail("G4-synthesis-has-template-vars")

    extracted = _extract_json("```json\n{\"findings\": [], \"overall_summary\": \"ok\"}\n```")
    parsed = json.loads(extracted)
    if "findings" in parsed:
        ok("G5-extract-json-markdown-block")
    else:
        fail("G5-extract-json-markdown-block")

    # Inline fallback: JSON object embedded in surrounding text (no markdown block)
    inline_input = 'some prefix {"findings": [], "overall_summary": "ok"} some suffix'
    extracted2 = _extract_json(inline_input)
    try:
        parsed2 = json.loads(extracted2)
        if "findings" in parsed2:
            ok("G6-extract-json-inline-fallback")
        else:
            fail("G6-extract-json-inline-fallback", f"parsed={parsed2}")
    except Exception as e2:
        fail("G6-extract-json-inline-fallback", str(e2))

    import inspect
    from backend.services.rag_service import RAGService
    src = inspect.getsource(RAGService.query)
    if "cited_indices" in src and "filtered_sources" in src:
        ok("G7-rag-citation-filtering")
    else:
        warn("G7-rag-citation-filtering", "No citation filtering in RAG service source")

except Exception as e:
    fail("G-grounding", str(e))


# =============================================================================
# H. FRONTEND TYPE CONTRACT (static)
# =============================================================================
section("H. FRONTEND TYPE CONTRACT (static)")

base = os.path.join(os.path.dirname(__file__), "..")
try:
    with open(os.path.join(base, "frontend", "src", "lib", "api.ts")) as f:
        api_ts = f.read()

    required = ["chunk_id","source_id","document_id","page_number","similarity_score","text","source_type","url"]
    missing = [f for f in required if f not in api_ts]
    if not missing:
        ok("H1-frontend-sourceref-all-fields")
    else:
        fail("H1-frontend-sourceref-all-fields", f"Missing: {missing}")

    if "'pdf' | 'web'" in api_ts:
        ok("H2-source-type-union-type")
    else:
        fail("H2-source-type-union-type")

    with open(os.path.join(base, "frontend", "src", "components", "evidence", "EvidencePanel.tsx")) as f:
        panel = f.read()

    if "sourceRef.text" in panel:
        ok("H3-evidencepanel-uses-sourceref-text")
    else:
        fail("H3-evidencepanel-uses-sourceref-text")

    if "chunkText" in panel:
        ok("H4-evidencepanel-retains-chunkcache-fallback")
    else:
        fail("H4-evidencepanel-retains-chunkcache-fallback")

    if "isWeb" in panel and "source_type" in panel:
        ok("H5-evidencepanel-web-branch")
    else:
        fail("H5-evidencepanel-web-branch")

    if "sourceRef.url" in panel:
        ok("H6-evidencepanel-renders-url")
    else:
        fail("H6-evidencepanel-renders-url")

    export_count = panel.count("export default function EvidencePanel")
    if export_count == 1:
        ok("H7-single-export")
    else:
        fail("H7-single-export", f"Found {export_count} export default")

    with open(os.path.join(base, "frontend", "src", "components", "research", "ResearchWorkspace.tsx")) as f:
        ws = f.read()

    if "runResearchDiscovery" in ws and "runResearch" in ws:
        ok("H8-workspace-real-api-functions")
    else:
        fail("H8-workspace-real-api-functions")

except Exception as e:
    fail("H-frontend", str(e))


# =============================================================================
# SUMMARY
# =============================================================================
print(f"\n{'='*60}")
print("  VALIDATION SUMMARY")
print(f"{'='*60}")

total = len(results)
passed = sum(1 for v in results.values() if v == "PASS")
warned = sum(1 for v in results.values() if v == "WARN")
failed = sum(1 for v in results.values() if v == "FAIL")

print(f"  Total: {total}  |  PASS: {passed}  |  WARN: {warned}  |  FAIL: {failed}")

if failed_checks := [k for k, v in results.items() if v == "FAIL"]:
    print(f"\n  FAILED:")
    for k in failed_checks:
        print(f"    - {k}")

if warned_checks := [k for k, v in results.items() if v == "WARN"]:
    print(f"\n  WARNED:")
    for k in warned_checks:
        print(f"    - {k}")

print()
if failed == 0:
    print("  OVERALL: ALL CHECKS PASSED (or WARNED)")
else:
    print(f"  OVERALL: {failed} FAILURE(S) — fix before deployment")
print("  LLM/API calls: 0")
