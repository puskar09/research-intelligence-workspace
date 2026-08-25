import sys
import os

sys.path.insert(0, ".")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from backend.db.database import SessionLocal
from backend.services.context_builder import ContextBuilder
from backend.services.retrieval_service import RetrievalService
from backend.services.rag_service import _build_prompt

query = "What happens if a person is convicted of an offence under section 35 or 37?"
top_k = 5

db = SessionLocal()
retrieval_service = RetrievalService()
context_builder = ContextBuilder()

chunks = retrieval_service.search(db=db, query=query, top_k=top_k)

print(f"--- Retrieved {len(chunks)} chunks ---")
for i, chunk in enumerate(chunks):
    print(f"CHUNK {i+1} (page {chunk.page_number}, sim {chunk.similarity_score}):")
    print(chunk.text)
    print("-" * 40)

context_text, sources = context_builder.build(chunks)
prompt = _build_prompt(context=context_text, question=query)

print("\n--- FINAL ASSEMBLED PROMPT ---")
print(prompt)
print("------------------------------")
