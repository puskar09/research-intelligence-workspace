from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class Page(BaseModel):
    """A single page extracted from a Document."""

    page_number: int
    text: str
    char_count: int


class Document(BaseModel):
    """A processed document produced from a Source."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    filename: str
    document_type: str
    pages: list[Page]
    total_pages: int
    total_chars: int
    extracted_at: datetime