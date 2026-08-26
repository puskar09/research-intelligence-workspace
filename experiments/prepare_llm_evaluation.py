import os
import json
import requests
import time

BASE_URL = "http://127.0.0.1:8001"
DATASET_PATH = "evaluation/dataset.json"
OUTPUT_PATH = "evaluation/results/llm_evaluation_cases.json"

def main():
    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: {DATASET_PATH} not found.")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    evaluation_cases = []
    
    print(f"Preparing {len(dataset)} evaluation cases for LLM Judge...")

    for i, case in enumerate(dataset):
        print(f"[{i+1}/{len(dataset)}] Processing: {case['question']}")
        
        # 1. Fetch retrieved chunks
        retrieved_chunks = []
        try:
            r_search = requests.post(f"{BASE_URL}/api/search", json={"query": case["question"], "top_k": 5}, timeout=30)
            if r_search.status_code == 200:
                results = r_search.json().get("results", [])
                for res in results:
                    retrieved_chunks.append({
                        "text": res.get("text"),
                        "page_number": res.get("page_number"),
                        "source_id": res.get("source_id"),
                        "document_id": res.get("document_id")
                    })
            else:
                print(f"  Warning: Search API returned {r_search.status_code}")
        except Exception as e:
            print(f"  Warning: Search API failed: {e}")

        # 2. Fetch generated RAG answer
        generated_answer = None
        citations = []
        rag_metadata = {}
        latency = 0.0
        status = "success"
        
        start_time = time.time()
        try:
            r_rag = requests.post(f"{BASE_URL}/api/rag/query", json={"query": case["question"]}, timeout=60)
            latency = time.time() - start_time
            if r_rag.status_code == 200:
                data = r_rag.json()
                generated_answer = data.get("answer")
                citations = data.get("sources", [])
                rag_metadata = data.get("metadata", {})
            elif r_rag.status_code in [429, 502]:
                print(f"  Note: RAG answer unavailable (Rate limit {r_rag.status_code})")
                generated_answer = "unavailable (quota exceeded)"
                status = "error (quota)"
            else:
                print(f"  Warning: RAG API returned {r_rag.status_code}")
                generated_answer = f"unavailable (HTTP {r_rag.status_code})"
                status = f"error ({r_rag.status_code})"
        except Exception as e:
            latency = time.time() - start_time
            if "429" in str(e) or "502" in str(e):
                print(f"  Note: RAG answer unavailable (Rate limit)")
                generated_answer = "unavailable (quota exceeded)"
                status = "error (quota)"
            else:
                print(f"  Warning: RAG API failed: {e}")
                generated_answer = "unavailable (error)"
                status = "error (exception)"

        # 3. Build evaluation case
        eval_case = {
            "id": case["id"],
            "question": case["question"],
            "answerable": case["answerable"],
            "expected_pages": case.get("expected_pages", []),
            "expected_keywords": case.get("expected_keywords", []),
            "retrieved_chunks": retrieved_chunks,
            "generated_answer": generated_answer,
            "citations": citations,
            "rag_metadata": rag_metadata,
            "latency": latency,
            "status": status
        }
        
        evaluation_cases.append(eval_case)
        
        # Small delay to avoid aggressive API hammering if quota is somehow available
        time.sleep(2)

    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    # Save the output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(evaluation_cases, f, indent=2)
        
    success_count = sum(1 for c in evaluation_cases if c["status"] == "success")
    error_count = len(evaluation_cases) - success_count
    
    print(f"\nSuccessfully prepared {len(evaluation_cases)} cases.")
    print(f"Generations Successful: {success_count}")
    print(f"Generations Failed: {error_count}")
    print(f"Saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
