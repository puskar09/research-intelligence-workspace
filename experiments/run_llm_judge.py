import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

# We use the anthropic SDK to query Claude directly as the judge.
try:
    import anthropic
except ImportError:
    print("anthropic SDK not installed. Please install it.")
    exit(1)

INPUT_PATH = "evaluation/results/llm_evaluation_cases.json"
RESULTS_PATH = "evaluation/results/llm_judge_results.json"
SUMMARY_PATH = "evaluation/results/llm_judge_summary.json"

JUDGE_PROMPT = """You are an impartial, strict evaluator assessing a Retrieval-Augmented Generation (RAG) system.

You will be provided with:
1. QUESTION: The original question asked by the user.
2. ANSWERABLE: Whether the question is actually answerable from the retrieved evidence (True/False).
3. RETRIEVED_EVIDENCE: The chunks of text retrieved by the system, including their page numbers.
4. GENERATED_ANSWER: The final answer produced by the RAG system.
5. CITATIONS: The citations returned by the RAG system.

Your task is to evaluate the GENERATED_ANSWER based ONLY on the RETRIEVED_EVIDENCE provided. Do not use outside knowledge.

Return a STRICT JSON object with the following schema:
{{
  "correctness": 1-5,          // How correct is the answer in addressing the question based on the evidence? (1 = completely wrong/irrelevant, 5 = perfectly correct)
  "faithfulness": 1-5,         // Is the answer faithful to the evidence? (1 = completely hallucinates or contradicts evidence, 5 = perfectly faithful to evidence)
  "citation_correctness": 1-5, // Do the citations correctly point to the chunks where the information is found? (1 = no/wrong citations, 5 = perfect citations)
  "completeness": 1-5,         // Does the answer completely address the question using the available evidence? (1 = very incomplete, 5 = fully complete)
  "hallucination": true/false, // Did the model include any information NOT present in the retrieved evidence? (true = hallucinated, false = no hallucination)
  "abstention_correct": true/false, // If ANSWERABLE is false, did the model correctly abstain from answering? If ANSWERABLE is true, did it answer? (true = behaved correctly, false = behaved incorrectly)
  "reason": "..."              // A brief, 1-3 sentence explanation of your scores.
}}

Ensure your response is valid JSON only, without markdown wrapping or backticks.

Input Data:
QUESTION: {question}
ANSWERABLE: {answerable}
RETRIEVED_EVIDENCE:
{evidence}

GENERATED_ANSWER:
{answer}

CITATIONS:
{citations}
"""

def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found.")
        return

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    
    results = []
    
    total_evals = 0
    skipped_evals = 0
    failures = 0
    
    metrics = {
        "correctness": [],
        "faithfulness": [],
        "citation_correctness": [],
        "completeness": [],
        "hallucination": [],
        "abstention_correct": []
    }
    
    print(f"Starting LLM Judge evaluation for {len(cases)} cases using model {model}...")
    
    for i, case in enumerate(cases):
        print(f"\n[{i+1}/{len(cases)}] Judging question: {case['question']}")
        
        if case.get("status") != "success":
            print(f"  Skipping (case status: {case.get('status')})")
            skipped_evals += 1
            results.append({
                "id": case["id"],
                "skipped": True,
                "reason": f"Case generation failed with status {case.get('status')}"
            })
            continue
            
        evidence_str = ""
        for idx, chunk in enumerate(case.get("retrieved_chunks", [])):
            evidence_str += f"--- Chunk {idx+1} (Page {chunk.get('page_number')}) ---\n{chunk.get('text')}\n\n"
            
        prompt = JUDGE_PROMPT.format(
            question=case["question"],
            answerable=case["answerable"],
            evidence=evidence_str,
            answer=case["generated_answer"],
            citations=json.dumps(case.get("citations", []), indent=2)
        )
        
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON out of response
            response_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    response_text = block.text
                    break
            if not response_text:
                raise ValueError("No text block found in response")
            # Try to strip markdown JSON block if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            judgement = json.loads(response_text)
            
            result_case = {
                "id": case["id"],
                "skipped": False,
                "judgement": judgement,
                "evaluator_failure": False
            }
            results.append(result_case)
            
            metrics["correctness"].append(judgement.get("correctness", 0))
            metrics["faithfulness"].append(judgement.get("faithfulness", 0))
            metrics["citation_correctness"].append(judgement.get("citation_correctness", 0))
            metrics["completeness"].append(judgement.get("completeness", 0))
            metrics["hallucination"].append(judgement.get("hallucination", True))
            metrics["abstention_correct"].append(judgement.get("abstention_correct", False))
            
            print("  [SUCCESS] Judgement parsed.")
            total_evals += 1
            
        except Exception as e:
            print(f"  [ERROR] Judge API or parsing failed: {e}")
            failures += 1
            results.append({
                "id": case["id"],
                "skipped": False,
                "evaluator_failure": True,
                "error": str(e)
            })
            
        time.sleep(2) # rate limit prevention

    # Compute aggregates
    def avg(lst):
        return sum(lst)/len(lst) if lst else 0.0
        
    hallucination_rate = sum(1 for x in metrics["hallucination"] if x is True) / len(metrics["hallucination"]) if metrics["hallucination"] else 0.0
    abstention_rate = sum(1 for x in metrics["abstention_correct"] if x is True) / len(metrics["abstention_correct"]) if metrics["abstention_correct"] else 0.0
    
    summary = {
        "cases_evaluated": total_evals,
        "cases_skipped": skipped_evals,
        "evaluator_failures": failures,
        "average_correctness": avg(metrics["correctness"]),
        "average_faithfulness": avg(metrics["faithfulness"]),
        "average_citation_correctness": avg(metrics["citation_correctness"]),
        "average_completeness": avg(metrics["completeness"]),
        "hallucination_rate": hallucination_rate,
        "correct_abstention_rate": abstention_rate
    }
    
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Evaluated: {total_evals}")
    print(f"Skipped:   {skipped_evals}")
    print(f"Failures:  {failures}")
    print(f"Avg Correctness:          {summary['average_correctness']:.2f}/5.0")
    print(f"Avg Faithfulness:         {summary['average_faithfulness']:.2f}/5.0")
    print(f"Avg Citation Correctness: {summary['average_citation_correctness']:.2f}/5.0")
    print(f"Avg Completeness:         {summary['average_completeness']:.2f}/5.0")
    print(f"Hallucination Rate:       {summary['hallucination_rate']*100:.1f}%")
    print(f"Correct Abstention Rate:  {summary['correct_abstention_rate']*100:.1f}%")
    print("========================================")

if __name__ == "__main__":
    main()
