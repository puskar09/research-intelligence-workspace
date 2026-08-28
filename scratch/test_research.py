import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.database import SessionLocal
from backend.services.retrieval_service import RetrievalService
from backend.services.llm_service import ClaudeLLMService
from backend.services.research_service import ResearchService
from backend.services.web_research_service import WebResearchService

def main():
    print("Testing ResearchService against DB...")
    try:
        db = SessionLocal()
        llm = ClaudeLLMService()
        retrieval = RetrievalService()
        web = WebResearchService()
        research = ResearchService(
            retrieval_service=retrieval, 
            llm_service=llm, 
            web_research_service=web
        )

        query = "What are the requirements under Section 17 of the FCRA?"
        print(f"Executing query: {query}")
        
        # We set web_search=True to test the batched embedding performance
        result = research.query(db=db, question=query, web_search=True)
        
        print("\n--- SYNTHESIS RESULTS ---")
        print(f"Overall Summary: {result.overall_summary}")
        print(f"Findings Count: {len(result.findings)}")
        for i, f in enumerate(result.findings):
            print(f"\nFinding {i+1}:")
            print(f"  SubQ: {f.sub_question}")
            print(f"  Insufficient: {f.insufficient_evidence}")
            print(f"  Evidence: {f.evidence[:150]}...")
            
    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
