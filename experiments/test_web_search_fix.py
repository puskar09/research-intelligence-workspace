import asyncio
import sys
import logging

from backend.services.research_service import ResearchService
from backend.services.retrieval_service import RetrievalService, RetrievalResult
from backend.services.context_builder import ContextBuilder
from backend.services.llm_service import ClaudeLLMService
from backend.services.web_research_service import WebResearchService, WebChunk
from backend.services.source_ranker import SourceRanker
from backend.db.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockRetrievalService(RetrievalService):
    def __init__(self, mock_results=None):
        self.mock_results = mock_results or []
        
    def search(self, db, query, top_k=5):
        # Always return the mock local results, sorted by cosine distance
        return sorted(self.mock_results, key=lambda x: x.cosine_distance)[:top_k]


def run_test(name: str, local_chunks, web_search: bool):
    print(f"\n{'='*50}\nTEST: {name}\n{'='*50}")
    
    svc = ResearchService(
        retrieval_service=MockRetrievalService(local_chunks),
        llm_service=ClaudeLLMService(),
        context_builder=ContextBuilder(),
        web_research_service=WebResearchService(),
        source_ranker=SourceRanker()
    )
    
    db = SessionLocal()
    try:
        res = svc.query(db, "What is the history of the Eiffel Tower?", web_search=web_search)
        
        web_count = sum(1 for s in res.sources if s.source_type == 'web')
        local_count = sum(1 for s in res.sources if s.source_type == 'pdf' or s.source_type != 'web')
        
        print(f"\nRESULTS for {name}:")
        print(f"Total Sources: {len(res.sources)}")
        print(f"Local Sources: {local_count}")
        print(f"Web Sources:   {web_count}")
        
        for s in res.sources:
            print(f" - [{s.source_type}] sim={s.similarity_score:.4f} url={s.url or 'local'} text={s.text[:50]}...")
            
    finally:
        db.close()

if __name__ == "__main__":
    highly_relevant_local = [
        RetrievalResult(chunk_id="L1", text="The Eiffel Tower was built in 1889.", cosine_distance=0.05, similarity_score=0.95, source_id="pdf1", document_id="local_pdf", page_number=1, chunk_index=1),
        RetrievalResult(chunk_id="L2", text="It was designed by Gustave Eiffel for the World's Fair.", cosine_distance=0.06, similarity_score=0.94, source_id="pdf1", document_id="local_pdf", page_number=1, chunk_index=2),
        RetrievalResult(chunk_id="L3", text="The tower was initially criticized by some of France's leading artists.", cosine_distance=0.07, similarity_score=0.93, source_id="pdf1", document_id="local_pdf", page_number=2, chunk_index=1),
        RetrievalResult(chunk_id="L4", text="It is 330 meters tall.", cosine_distance=0.08, similarity_score=0.92, source_id="pdf1", document_id="local_pdf", page_number=2, chunk_index=2),
    ]

    # Scenario 2: PDF + web OFF
    run_test("PDF + web OFF", highly_relevant_local, web_search=False)
    
    # Scenario 3: PDF + web ON
    run_test("PDF + web ON", highly_relevant_local, web_search=True)
    
    # Scenario 4: web ON with no PDF/local sources
    run_test("web ON with no PDF/local", [], web_search=True)
