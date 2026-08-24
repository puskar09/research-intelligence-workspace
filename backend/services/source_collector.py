"""
SourceCollector — fetches a URL, extracts text content, and returns a
(Source, Document) pair so URL content flows through the same pipeline as PDFs.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime

from backend.models.source import Source
from backend.models.document import Document, Page


class SourceCollectionError(Exception):
    """Raised when a URL cannot be fetched or parsed."""


class SourceCollector:

    def collect(self, url: str) -> tuple[Source, Document]:
        """
        Fetch a URL, extract its text, and return a Source + Document.

        The document has a single page (page_number=1) containing the
        cleaned body text. This keeps URL content compatible with the
        per-page chunker.

        Args:
            url: The URL to fetch.

        Raises:
            SourceCollectionError: If the request fails or the URL is invalid.
        """
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
        except requests.exceptions.MissingSchema as exc:
            raise SourceCollectionError(
                f"Invalid URL (missing scheme): {url}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise SourceCollectionError(
                f"Could not connect to: {url}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise SourceCollectionError(
                f"Request timed out for: {url}"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise SourceCollectionError(
                f"HTTP error {response.status_code} for: {url}"
            ) from exc

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for element in soup(["script", "style", "noscript", "nav", "footer"]):
            element.decompose()

        # Prefer <title> tag for the page title; fall back to first <h1>
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else "Untitled"

        content = soup.get_text(separator=" ", strip=True)

        source = Source(
            url=url,
            title=title,
            source_type="url",
            created_at=datetime.now(),
        )

        page = Page(
            page_number=1,
            text=content,
            char_count=len(content),
        )

        document = Document(
            source_id=source.id,
            filename=url,
            document_type="url",
            pages=[page],
            total_pages=1,
            total_chars=len(content),
            extracted_at=datetime.now(),
        )

        return source, document