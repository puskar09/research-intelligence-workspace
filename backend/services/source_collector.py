import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pydantic import BaseModel


class Source(BaseModel):
    url: str
    title: str
    author: str | None = None
    published_at: str | None = None
    content: str
    extracted_at: str


class SourceCollector:

    def collect(self, url: str) -> Source:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        title_element = soup.find("h1")

        title = (
            title_element.get_text(strip=True)
            if title_element
            else "Untitled"
        )

        content = soup.get_text(separator=" ", strip=True)

        return Source(
            url=url,
            title=title,
            content=content,
            extracted_at=datetime.now().isoformat(),
        )