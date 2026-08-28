# API Reference

The Research Intelligence Workspace utilizes a FastAPI backend. Below are the primary endpoints exposed for the frontend and external integrations.

> **Swagger UI**: When running locally, you can view the interactive OpenAPI documentation at `http://localhost:8001/docs`.

---

## Sources

### `POST /api/sources/pdf`
Uploads and ingests a PDF document into the vector database.
- **Content-Type**: `multipart/form-data`
- **Body**: `file` (UploadFile)
- **Response**: Returns the created `Document` metadata, including the number of chunks processed.

### `POST /api/sources/url`
Scrapes a URL, extracts text, chunks it, and saves it to the vector database.
- **Content-Type**: `application/json`
- **Body**: 
  ```json
  {
    "url": "https://example.com/article"
  }
  ```
- **Response**: Returns the created `Document` metadata.

---

## Search & RAG

### `POST /api/search`
Performs a raw semantic vector search against local documents.
- **Body**:
  ```json
  {
    "query": "search term",
    "top_k": 5
  }
  ```
- **Response**: Array of `RetrievalResult` objects containing similarity scores and chunk text.

### `POST /api/rag/query`
Standard Retrieval-Augmented Generation (RAG). Fetches chunks and generates a single synthesized answer.
- **Body**:
  ```json
  {
    "query": "user question"
  }
  ```
- **Response**: Returns the text `answer` and an array of `sources` cited by the LLM.

---

## Research Workflow

### `POST /api/research/discover`
Exploratory endpoint that takes a broad topic and generates focused research questions categorized by domain.
- **Body**:
  ```json
  {
    "topic": "FCRA Act",
    "web_search": false
  }
  ```
- **Response**: 
  ```json
  {
    "topic": "FCRA Act",
    "questions": [
      {
        "id": "q1",
        "question": "What are the registration requirements?",
        "category": "Legal"
      }
    ]
  }
  ```

### `POST /api/research/query`
The heavy-lifting orchestration endpoint. Executes the full multi-step research pipeline.
- **Body**:
  ```json
  {
    "query": "Detailed research question",
    "web_search": true
  }
  ```
- **Response**:
  ```json
  {
    "original_query": "...",
    "sub_questions": ["..."],
    "findings": [
      {
        "sub_question": "...",
        "evidence": "...",
        "insufficient_evidence": false
      }
    ],
    "overall_summary": "...",
    "sources": [
      {
        "chunk_id": "...",
        "text": "...",
        "source_type": "pdf"
      }
    ]
  }
  ```

---

## System

### `GET /health`
Simple health check endpoint.
- **Response**: `{"status": "ok"}`
