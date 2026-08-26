import json
import logging
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.api.research import router
from backend.main import app
from backend.services.research_discovery import ResearchDiscoveryService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mocked_discovery():
    # Patch the discovery service
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '''
    `json
    {
      "topic": "FCRA Act",
      "questions": [
        {"id": "q1", "question": "What is FCRA?", "category": "Legal"},
        {"id": "q2", "question": "How does FCRA impact banks?", "category": "Finance"},
        {"id": "q3", "question": "What are the penalties?", "category": "Compliance"},
        {"id": "q4", "question": "When was it enacted?", "category": "History"},
        {"id": "q5", "question": "Who enforces it?", "category": "Regulatory"}
      ]
    }
    `
    '''
    
    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = []
    
    svc = ResearchDiscoveryService(llm_service=mock_llm, retrieval_service=mock_retrieval)
    
    # Overwrite the global instance
    import backend.api.research as research_api
    research_api._discovery_service = svc
    
    client = TestClient(app)
    
    # 1. Validation test
    response = client.post("/api/research/discover", json={"web_search": False})
    assert response.status_code == 422, "Should fail on missing topic"
    
    # 2. Mock discovery request
    response = client.post("/api/research/discover", json={"topic": "FCRA Act", "web_search": False})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert data["topic"] == "FCRA Act"
    assert len(data["questions"]) == 5
    assert data["questions"][0]["id"] == "q1"
    
    # 3. Cache test
    response2 = client.post("/api/research/discover", json={"topic": "FCRA Act", "web_search": False})
    assert response2.status_code == 200
    
    # Ensure LLM was only called once due to cache
    mock_llm.generate.assert_called_once()
    
    logger.info("Mocked discovery tests passed.")
    return True

def test_live_discovery():
    import backend.api.research as research_api
    research_api._discovery_service = None  # Reset to use real services
    
    client = TestClient(app)
    
    logger.info("Running ONE live Claude discovery request...")
    response = client.post("/api/research/discover", json={"topic": "Climate Change Policy", "web_search": True})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert data["topic"] == "Climate Change Policy"
    assert 5 <= len(data["questions"]) <= 10, f"Expected 5-10 questions, got {len(data['questions'])}"
    
    q_ids = set([q["id"] for q in data["questions"]])
    assert len(q_ids) == len(data["questions"]), "Duplicate question IDs found"
    
    logger.info("Live discovery test passed. Questions generated:")
    for q in data["questions"]:
        logger.info(f" - [{q['category']}] {q['question']}")

if __name__ == "__main__":
    test_mocked_discovery()
    test_live_discovery()
    logger.info("Phase 9 verification complete!")
