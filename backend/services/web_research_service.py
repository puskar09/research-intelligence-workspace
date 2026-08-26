import logging
import uuid
import re
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Search Provider Abstraction
# ---------------------------------------------------------------------------

class BaseWebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 2) -> List[str]:
        """Return a list of URLs relevant to the query."""
        pass


class DDGLiteSearchProvider(BaseWebSearchProvider):
    def search(self, query: str, max_results: int = 2) -> List[str]:
        url = "https://lite.duckduckgo.com/lite/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        data = {"q": query}
        urls = []
        try:
            r = requests.post(url, data=data, headers=headers, timeout=5)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            # The result links in DDG Lite are usually in <a> tags within a table or with specific classes.
            # Usually the result links have class 'result-url' or are within standard links.
            for a in soup.find_all('a', class_='result-url'):
                href = a.get('href')
                if href and href.startswith("http") and not "duckduckgo.com" in href:
                    urls.append(href)
                    if len(urls) >= max_results:
                        break
                        
            # Fallback if 'result-url' class is not present
            if not urls:
                for a in soup.find_all('a'):
                    href = a.get('href')
                    # Very basic filter to avoid internal links
                    if href and href.startswith("http") and "duckduckgo.com" not in href:
                        urls.append(href)
                        if len(urls) >= max_results:
                            break
                            
        except Exception as exc:
            logger.warning("DDG Lite search failed for query %r: %s", query, exc)
            
        if not urls:
            urls = ["https://en.wikipedia.org/wiki/Main_Page"]
            
        return urls


# ---------------------------------------------------------------------------
# Web Research Service
# ---------------------------------------------------------------------------

@dataclass
class WebChunk:
    chunk_id: str
    text: str
    url: str
    chunk_index: int


class WebResearchService:
    def __init__(self, search_provider: BaseWebSearchProvider = None):
        self._provider = search_provider or DDGLiteSearchProvider()
        self.timeout = 5
        
    def _fetch_text(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            r = requests.get(url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            # Remove excessive whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return ""

    def _chunk_text(self, text: str, url: str, max_words: int = 150) -> List[WebChunk]:
        if not text:
            return []
        
        words = text.split()
        chunks = []
        chunk_index = 0
        for i in range(0, len(words), max_words):
            chunk_words = words[i:i+max_words]
            chunk_text = " ".join(chunk_words)
            chunks.append(WebChunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk_text,
                url=url,
                chunk_index=chunk_index
            ))
            chunk_index += 1
        return chunks

    def get_web_chunks(self, query: str, max_urls: int = 2) -> List[WebChunk]:
        """Search the web, fetch URLs, and return chunks of text."""
        urls = self._provider.search(query, max_results=max_urls)
        all_chunks = []
        for url in urls:
            text = self._fetch_text(url)
            if text:
                all_chunks.extend(self._chunk_text(text, url))
        
        logger.info("WebResearch: found %d chunks from %d URLs for query %r", len(all_chunks), len(urls), query[:30])
        return all_chunks
