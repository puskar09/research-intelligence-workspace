import logging
from typing import List

from backend.services.embedding_service import embed_text, embed_texts
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
        web_chunk_vectors: List[List[float]] = None,
        top_k: int = 3,
        query_vector: List[float] = None
    ) -> List[RetrievalResult]:
        
        if not local_results and not web_chunks:
            return []

        # Create a combined list of local and web chunks
        ranked_local = list(local_results)
        ranked_local.sort(key=lambda x: x.cosine_distance)
        
        ranked_web = []
        if web_chunks:
            # Cap the number of web chunks to rank to avoid extreme payloads
            if not web_chunk_vectors and len(web_chunks) > 100:
                logger.info("SourceRanker: truncating %d web chunks to 100", len(web_chunks))
                web_chunks = web_chunks[:100]

            # Embed the query to compare with web chunks
            if query_vector is None:
                query_vector = embed_text(query)

            if web_chunk_vectors and len(web_chunk_vectors) == len(web_chunks):
                w_vecs = web_chunk_vectors
            else:
                # Batched embedding of all web chunks
                chunk_texts = [wchunk.text for wchunk in web_chunks]
                w_vecs = embed_texts(chunk_texts)

            # Compute distances
            for wchunk, w_vec in zip(web_chunks, w_vecs):
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
                ranked_web.append(res)
                
            ranked_web.sort(key=lambda x: x.cosine_distance)

        # Merge local and web chunks with diversity guarantee
        if not ranked_web:
            top_results = ranked_local[:top_k]
        elif not ranked_local:
            top_results = ranked_web[:top_k]
        else:
            # Both exist. Guarantee at least 1 web chunk if available.
            top_results = []
            
            # 1. Take the absolute best chunk overall
            best_local = ranked_local[0]
            best_web = ranked_web[0]
            
            # We want to force at least 1 web chunk in the top_k.
            # We take 1 web chunk and the rest from the combined pool.
            top_results.append(ranked_web.pop(0))
            
            # Pool the remaining chunks together and sort them by distance
            remaining_pool = ranked_local + ranked_web
            remaining_pool.sort(key=lambda x: x.cosine_distance)
            
            # Fill the rest of the top_k
            slots_left = top_k - 1
            if slots_left > 0:
                top_results.extend(remaining_pool[:slots_left])
                
            # Re-sort the final top_results by distance so they appear logically ordered
            top_results.sort(key=lambda x: x.cosine_distance)
            
        logger.info("SourceRanker: ranked total chunks, returning top %d", len(top_results))
        return top_results
