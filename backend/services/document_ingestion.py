"""
DocumentIngestion — converts a PDF file into a Document with Pages.

Uses the modern `import pymupdf` API (PyMuPDF >= 1.24).
"""

import pymupdf
from datetime import datetime
from pathlib import Path

from backend.models.document import Document, Page


class DocumentIngestionError(Exception):
    """Raised when a PDF cannot be ingested."""


class DocumentIngestion:

    def ingest_pdf(self, file_path: str, source_id: str) -> Document:
        """
        Open a PDF, extract text from each page, and return a Document.

        Args:
            file_path: Absolute or relative path to a PDF file.
            source_id: ID of the Source that owns this document.

        Raises:
            DocumentIngestionError: If the file does not exist, is not a PDF,
                                    or is completely empty.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentIngestionError(f"File not found: {file_path}")
        if path.suffix.lower() != ".pdf":
            raise DocumentIngestionError(
                f"Expected a PDF file, got: {path.suffix!r}"
            )

        try:
            pdf = pymupdf.open(str(path))
        except Exception as exc:
            raise DocumentIngestionError(
                f"Could not open PDF '{file_path}': {exc}"
            ) from exc

        if pdf.page_count == 0:
            pdf.close()
            raise DocumentIngestionError(
                f"PDF has no pages: {file_path}"
            )

        pages: list[Page] = []

        for index, pdf_page in enumerate(pdf):
            text = pdf_page.get_text("text")
            pages.append(
                Page(
                    page_number=index + 1,
                    text=text,
                    char_count=len(text),
                )
            )

        pdf.close()

        total_chars = sum(p.char_count for p in pages)

        return Document(
            source_id=source_id,
            filename=path.name,
            document_type="pdf",
            pages=pages,
            total_pages=len(pages),
            total_chars=total_chars,
            extracted_at=datetime.now(),
        )