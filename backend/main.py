from fastapi import FastAPI
from pydantic import BaseModel

from backend.services.source_collector import SourceCollector

app = FastAPI()

collector = SourceCollector()


class SourceRequest(BaseModel):
    url: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/sources")
def collect_source(request: SourceRequest):
    source = collector.collect(request.url)
    return source