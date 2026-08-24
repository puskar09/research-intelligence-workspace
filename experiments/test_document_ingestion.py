from backend.services.document_ingestion import DocumentIngestion

ingestion = DocumentIngestion()

document = ingestion.ingest_pdf("data/raw/test.pdf")

print("Filename:", document.filename)
print("Pages:", len(document.pages))

for page in document.pages:
    print(f"\n--- Page {page.page_number} ---")
    print("Characters:", len(page.text))
    print("Text:", repr(page.text[:200]))