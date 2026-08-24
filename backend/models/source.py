from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
import uuid


class Source(BaseModel):
    """Represents a raw input to the pipeline — a URL or an uploaded file."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # url is optional: uploaded PDFs may not have a URL
    url: str | None = None
    title: str
    source_type: Literal["pdf", "url"]
    created_at: datetime = Field(default_factory=datetime.now)
