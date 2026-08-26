import logging
from typing import List

from backend.services.embedding_service import embed_text
from backend.services.retrieval_service import RetrievalResult
from backend.services.web_research_service import WebChunk

logger = logging.getLogger(__name__)

def _cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine distance between two L2-normalized vectors."""
    # Assuming vec1 and vec2 are L2-normalized by embed_text
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    # distance = 1 - similarity
    # clamp to avoid float precision issues
    return max(0.0, 1.0 - dot_product)


class SourceRanker:
    """Ranks and combines local RetrievalResults and WebChunks."""

    def rank(
        self,
        query: str,
        local_results: List[RetrievalResult],
        web_chunks: List[WebChunk],
        top_k: int = 3
    ) -> List[RetrievalResult]:
        
        if not local_results and not web_chunks:
            return []

        combined: List[RetrievalResult] = list(local_results)

        if web_chunks:
            # Embed the query to compare with web chunks
            query_vector = embed_text(query)

            # Embed web chunks and compute distances
            for wchunk in web_chunks:
                w_vec = embed_text(wchunk.text)
                dist = _cosine_distance(query_vector, w_vec)
                sim = 1.0 - dist
                
                res = RetrievalResult(
                    chunk_id=wchunk.chunk_id,
                    text=wchunk.text,
                    cosine_distance=round(dist, 6),
                    similarity_score=round(sim, 6),
                    source_id="web",
                    document_id=wchunk.url,
                    page_number=1,
                    chunk_index=wchunk.chunk_index
                )
                combined.append(res)
                
        # Sort by cosine distance ascending (lowest distance = highest similarity)
        combined.sort(key=lambda x: x.cosine_distance)
        
        top_results = combined[:top_k]
        logger.info("SourceRanker: ranked %d total chunks, returning top %d", len(combined), len(top_results))
        return top_results
