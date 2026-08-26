import os
import json
import csv
import time
import requests
from typing import List, Dict, Any

BASE_URL = "http://127.0.0.1:8001"
DATASET_PATH = "evaluation/dataset.json"
RESULTS_DIR = "evaluation/results"
RESULTS_JSON = os.path.join(RESULTS_DIR, "phase7_results.json")
RESULTS_CSV = os.path.join(RESULTS_DIR, "phase7_results.csv")

def ensure_dirs():
    os.makedirs(RESULTS_DIR, exist_ok=True)

def is_chunk_relevant(chunk: Dict[str, Any], case: Dict[str, Any]) -> bool:
    if not case["answerable"]:
        return False
        
    expected_pages = case.get("expected_pages", [])
    expected_keywords = [" ".join(kw.lower().split()) for kw in case.get("expected_keywords", [])]
    
    # Simple heuristic: if the page matches, it's relevant
    if chunk.get("page_number") in expected_pages:
        return True
        
    # Or if text contains any expected keywords
    chunk_text = " ".join(chunk.get("text", "").lower().split())
    if any(kw in chunk_text for kw in expected_keywords):
        return True
        
    return False

def evaluate_retrieval(query: str, case: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    try:
        r = requests.post(f"{BASE_URL}/api/search", json={"query": query, "top_k": 5}, timeout=30)
        r.raise_for_status()
    except Exception as e:
        return {"error": str(e), "latency": time.time() - start_time, "recall_3": 0, "recall_5": 0, "results": []}
    
    latency = time.time() - start_time
    chunks = r.json().get("results", [])
    
    # Calculate Recall@3
    relevant_in_top_3 = False
    for chunk in chunks[:3]:
        if is_chunk_relevant(chunk, case):
            relevant_in_top_3 = True
            break
            
    # Calculate Recall@5
    relevant_in_top_5 = False
    for chunk in chunks[:5]:
        if is_chunk_relevant(chunk, case):
            relevant_in_top_5 = True
            break
            
    return {
        "recall_3": 1 if relevant_in_top_3 else 0,
        "recall_5": 1 if relevant_in_top_5 else 0,
        "latency": latency,
        "results": chunks
    }

def evaluate_generation(query: str, case: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    try:
        r = requests.post(f"{BASE_URL}/api/rag/query", json={"query": query}, timeout=60)
        if r.status_code in [429, 502]:
            return {"skipped": True, "reason": f"Rate limit / Quota exceeded ({r.status_code})"}
        r.raise_for_status()
    except Exception as e:
        if "429" in str(e) or "502" in str(e):
            return {"skipped": True, "reason": f"Rate limit / Quota exceeded ({e})"}
        return {"skipped": True, "reason": str(e)}
        
    latency = time.time() - start_time
    resp = r.json()
    answer = resp.get("answer", "")
    sources = resp.get("sources", [])
    
    if case["answerable"]:
        # Citation correctness: Does the sources array contain the expected page?
        expected_pages = case.get("expected_pages", [])
        cited_pages = [s.get("page_number") for s in sources]
        citation_correct = any(p in cited_pages for p in expected_pages)
        return {
            "skipped": False,
            "latency": latency,
            "citation_correct": 1 if citation_correct else 0,
            "insufficient_evidence_detected": 0
        }
    else:
        # Insufficient evidence detection
        is_insufficient = "insufficient" in answer.lower() or "not contain enough information" in answer.lower()
        return {
            "skipped": False,
            "latency": latency,
            "citation_correct": 0,
            "insufficient_evidence_detected": 1 if is_insufficient else 0
        }

def run_evaluation():
    ensure_dirs()
    
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    results = []
    
    print("============================================================")
    print("  Running Phase 7 Evaluation Framework")
    print("============================================================")
    
    total_q = len(dataset)
    for i, case in enumerate(dataset):
        print(f"[{i+1}/{total_q}] Evaluating: {case['question']}")
        
        retrieval_metrics = evaluate_retrieval(case["question"], case)
        generation_metrics = evaluate_generation(case["question"], case)
        
        result_entry = {
            "id": case["id"],
            "question": case["question"],
            "answerable": case["answerable"],
            "retrieval_latency": retrieval_metrics.get("latency", 0),
            "recall_3": retrieval_metrics.get("recall_3", 0),
            "recall_5": retrieval_metrics.get("recall_5", 0),
            "generation_skipped": generation_metrics.get("skipped", False),
            "generation_skip_reason": generation_metrics.get("reason", ""),
            "generation_latency": generation_metrics.get("latency", 0),
            "citation_correct": generation_metrics.get("citation_correct", 0),
            "insufficient_evidence_detected": generation_metrics.get("insufficient_evidence_detected", 0)
        }
        results.append(result_entry)
        
        # Friendly sleep to avoid hammering limits too aggressively if they do work
        if not generation_metrics.get("skipped"):
            time.sleep(2)
            
    # Save JSON
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    # Save CSV
    if results:
        keys = results[0].keys()
        with open(RESULTS_CSV, "w", encoding="utf-8", newline="") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
            
    print("\n============================================================")
    print("  Evaluation Summary")
    print("============================================================")
    print(f"Dataset Size: {total_q}")
    
    answerable_cases = [r for r in results if r["answerable"]]
    unanswerable_cases = [r for r in results if not r["answerable"]]
    
    if answerable_cases:
        avg_r3 = sum(r["recall_3"] for r in answerable_cases) / len(answerable_cases)
        avg_r5 = sum(r["recall_5"] for r in answerable_cases) / len(answerable_cases)
        print(f"Recall@3 (Answerable): {avg_r3:.2f}")
        print(f"Recall@5 (Answerable): {avg_r5:.2f}")
        
    avg_ret_lat = sum(r["retrieval_latency"] for r in results) / total_q
    print(f"Avg Retrieval Latency: {avg_ret_lat:.2f}s")
    
    skipped_gens = [r for r in results if r["generation_skipped"]]
    print(f"Skipped LLM Tests: {len(skipped_gens)}")
    if skipped_gens:
        print(f"  Reason: {skipped_gens[0]['generation_skip_reason']}")
        
    evaluated_gens = [r for r in results if not r["generation_skipped"]]
    if evaluated_gens:
        eval_answerable = [r for r in evaluated_gens if r["answerable"]]
        if eval_answerable:
            citation_acc = sum(r["citation_correct"] for r in eval_answerable) / len(eval_answerable)
            print(f"Citation Accuracy (Answerable): {citation_acc:.2f}")
            
        eval_unanswerable = [r for r in evaluated_gens if not r["answerable"]]
        if eval_unanswerable:
            insuff_acc = sum(r["insufficient_evidence_detected"] for r in eval_unanswerable) / len(eval_unanswerable)
            print(f"Insufficient-Evidence Accuracy (Unanswerable): {insuff_acc:.2f}")
            
        avg_gen_lat = sum(r["generation_latency"] for r in evaluated_gens) / len(evaluated_gens)
        print(f"Avg Generation Latency: {avg_gen_lat:.2f}s")
        
    print(f"\nResults saved to:")
    print(f" - {RESULTS_JSON}")
    print(f" - {RESULTS_CSV}")

if __name__ == "__main__":
    run_evaluation()
