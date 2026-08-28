# System Architecture & Pipelines

This document provides a detailed breakdown of the internal pipelines and data flow within the Research Intelligence Workspace.

The system is strictly divided into logical phases to separate the heavy processing (ingestion and embeddings) from the latency-sensitive operations (retrieval and LLM synthesis).

---

## High-Level Data Flow

1. **Ingestion**: Raw data (PDFs/URLs) is extracted and split.
2. **Embedding**: Text chunks are converted into mathematical vectors.
3. **Retrieval**: User queries fetch the most similar vectors.
4. **Ranking**: Results from multiple sources (local + web) are sorted by relevance.
5. **Synthesis**: An LLM reads the top-ranked text and generates a structured JSON report.

---

## 1. Document Ingestion Pipeline

When a user uploads a document, the following sequence occurs:

1. **Extraction**: Text is extracted from the PDF using PyMuPDF, preserving page numbers.
2. **Chunking**: The `Chunker` (`backend/services/chunker.py`) splits the text into ~1000-character segments. It attempts to respect natural paragraph breaks and guarantees overlap between chunks to prevent losing context.
3. **Embedding**: Each chunk is passed to the `EmbeddingService`.
4. **Persistence**: The original document metadata and the chunked vectors are saved to PostgreSQL via SQLAlchemy.

---

## 2. Web Research Pipeline

When `web_search=true` is provided, the system does not just rely on local documents:

1. **Search Query**: The query is sent to a lightweight search provider (e.g., DuckDuckGo) to retrieve relevant URLs.
2. **Scraping**: The `WebResearchService` fetches the raw HTML from those URLs and extracts clean text using BeautifulSoup.
3. **Dynamic Chunking**: The scraped text is immediately chunked in memory.
4. **Evaluation**: These temporary web chunks are pushed to the `SourceRanker` to compete against the user's local database chunks.

> **Note**: Web search inherently introduces latency (network requests, potential 403 blocks). The system gracefully handles failed fetches by falling back to local data.

---

## 3. The Research Orchestrator

The core logic of the application lives in the `ResearchService` (`backend/services/research_service.py`). 
It executes a multi-step Agentic workflow:

### A. Sub-Question Generation
Instead of sending a complex user prompt directly to vector search (which often yields poor similarity matching), the LLM is first asked to decompose the user's topic into 3-5 highly specific **sub-questions**.

### B. Iterative Retrieval
For *each* sub-question, the system runs an independent vector search against PostgreSQL and an independent Web Search.

### C. Source Ranking & Optimization
The `SourceRanker` takes all retrieved chunks (local and web) across all sub-questions and computes their exact Cosine Distance against the queries. 
*Engineering Note*: To prevent upstream timeouts, web chunk embeddings are processed in highly optimized **batches** (`embed_texts`) rather than sequentially.

### D. Context Building
The `ContextBuilder` aggregates the top chunks, strips duplicates, and assigns a strict numeric citation index (e.g., `[1]`, `[2]`) to each piece of text.

### E. LLM Synthesis & Hallucination Mitigation
The LLM is provided with the final context and the list of sub-questions. It must output strict JSON.
Crucially, if the context does not contain the answer, the LLM is prompted to set `insufficient_evidence: true` for that specific finding, heavily mitigating hallucinated answers.

If the LLM's output is truncated or malformed, the orchestrator triggers a single, bounded **repair retry** prompt, supplying the parser error back to the LLM to fix the syntax natively.
