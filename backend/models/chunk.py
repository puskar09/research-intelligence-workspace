from pydantic import BaseModel, Field
import uuid


class Chunk(BaseModel):
    """A text chunk produced by splitting a Document page."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    document_id: str
    # Every chunk maps to exactly one page — required for reliable RAG attribution.
    page_number: int
    chunk_index: int   # 0-based index within the page
    text: str
    char_count: int
    # Config used to produce this chunk — stored for reproducibility.
    chunk_size: int
    overlap: int
