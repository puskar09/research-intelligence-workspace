import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.main import app
from backend.db.database import SessionLocal
from backend.db.orm_models import SourceORM, DocumentORM, PageORM, ChunkORM

def main():
    print("Testing source deletion cascade...")
    client = TestClient(app)
    db = SessionLocal()
    
    try:
        print("Ingesting test URL...")
        resp = client.post("/api/sources/url", json={"url": "https://example.com/"})
        assert resp.status_code == 200, f"Ingestion failed: {resp.text}"
        data = resp.json()
        src_id = data["source"]["id"]
        doc_id = data["document"]["id"]
        print(f"Created Source: {src_id}")
        
        # 3-7. Verify Source data exists in DB
        assert db.query(SourceORM).filter(SourceORM.id == src_id).count() == 1, "Source missing"
        assert db.query(DocumentORM).filter(DocumentORM.source_id == src_id).count() == 1, "Document missing"
        
        c_count = db.query(ChunkORM).filter(ChunkORM.source_id == src_id).count()
        assert c_count > 0, "Chunks missing"
        c_orm = db.query(ChunkORM).filter(ChunkORM.source_id == src_id).first()
        assert c_orm.embedding is not None, "Embedding missing"
        print(f"Verified Source {src_id} and {c_count} chunks exist.")

        # 8-9. Call DELETE endpoint
        print("Calling DELETE endpoint...")
        del_resp = client.delete(f"/api/sources/{src_id}")
        assert del_resp.status_code == 204, f"Delete failed: {del_resp.text}"
        print("Delete endpoint succeeded (204).")

        # 10-14. Verify Source data is gone
        assert db.query(SourceORM).filter(SourceORM.id == src_id).count() == 0, "Source still exists"
        assert db.query(DocumentORM).filter(DocumentORM.source_id == src_id).count() == 0, "Document still exists"
        assert db.query(PageORM).filter(PageORM.document_id == doc_id).count() == 0, "Page still exists"
        assert db.query(ChunkORM).filter(ChunkORM.source_id == src_id).count() == 0, "Chunk/Embedding still exists"
        print("Verified cascade deletion completely cleaned up DB.")
        
        # 16. Verify 404 on nonexistent
        print("Testing 404 behavior...")
        resp404 = client.delete(f"/api/sources/{src_id}")
        assert resp404.status_code == 404, "Did not get 404 for deleted source"
        print("404 test passed.")
        
        print("All tests passed.")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
