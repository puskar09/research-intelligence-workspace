const API_PREFIX = '/api/backend';

// Schemas based on FastAPI models

export interface Source {
  id: string;
  url: string | null;
  title: string;
  source_type: string;
}

export interface DocumentSummary {
  id: string;
  source_id: string;
  filename: string;
  document_type: string;
  total_pages: int;
  total_chars: int;
  extracted_at: string;
}

export interface Chunk {
  id: string;
  source_id: string;
  document_id: string;
  page_number: int;
  chunk_index: int;
  text: string;
  char_count: int;
}

export interface ChunkStats {
  total_chunks: int;
  chunk_size: int;
  overlap: int;
  chunks_embedded: int;
}

export interface IngestionResponse {
  source: Source;
  document: DocumentSummary;
  chunks: Chunk[];
  stats: ChunkStats;
}

export interface SourceRef {
  chunk_id: string;
  source_id: string;
  document_id: string;
  page_number: int;
  similarity_score: float;
  // Optional enriched fields — null when unavailable
  text?: string | null;
  source_type?: 'pdf' | 'web' | null;
  url?: string | null;
}

export interface RAGMetadata {
  model: string;
  chunks_retrieved: int;
  context_chars: int;
  top_k: int;
}

export interface RAGQueryResponse {
  answer: string;
  sources: SourceRef[];
  metadata: RAGMetadata;
}

export interface FindingModel {
  sub_question: string;
  evidence: string;
  insufficient_evidence: boolean;
}

export interface ResearchMetadata {
  model: string;
  chunks_retrieved: int;
  context_chars: int;
}

export interface ResearchQueryResponse {
  original_query: string;
  sub_questions: string[];
  findings: FindingModel[];
  overall_summary: string;
  sources: SourceRef[];
  metadata: ResearchMetadata;
}

export interface DiscoveryQuestion {
  id: string;
  question: string;
  category: string;
}

export interface ResearchDiscoveryResponse {
  topic: string;
  questions: DiscoveryQuestion[];
}

type int = number;
type float = number;

export async function uploadPdf(file: File): Promise<IngestionResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_PREFIX}/sources/pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`PDF Upload failed: ${error}`);
  }

  return res.json();
}

export async function ingestUrl(url: string): Promise<IngestionResponse> {
  const res = await fetch(`${API_PREFIX}/sources/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`URL Ingestion failed: ${error}`);
  }

  return res.json();
}

export async function askQuestion(query: string, topK: number = 5): Promise<RAGQueryResponse> {
  const res = await fetch(`${API_PREFIX}/rag/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Ask query failed: ${error}`);
  }

  return res.json();
}

export async function runResearch(query: string, webSearch: boolean = false): Promise<ResearchQueryResponse> {
  const res = await fetch(`${API_PREFIX}/research/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, web_search: webSearch }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Research query failed: ${error}`);
  }

  return res.json();
}

export async function runResearchDiscovery(topic: string, webSearch: boolean = false): Promise<ResearchDiscoveryResponse> {
  const res = await fetch(`${API_PREFIX}/research/discover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, web_search: webSearch }),
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Discovery failed: ${error}`);
  }

  return res.json();
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await fetch(`${API_PREFIX}/sources/${sourceId}`, {
    method: 'DELETE',
  });

  if (!res.ok) {
    let errorMsg = 'Unknown error';
    try {
      errorMsg = await res.text();
    } catch (e) {
      // ignore
    }
    throw new Error(`Delete failed: ${errorMsg}`);
  }
}
