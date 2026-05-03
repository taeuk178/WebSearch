from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import SearchResult


@dataclass(frozen=True)
class ReadDocument:
    result: SearchResult
    text: str
    from_page: bool = False
    chunks: list[str] | None = None
    title: str | None = None
    url: str | None = None
    published_at: str | None = None
    source_type: str | None = None


class PageReader(ABC):
    @abstractmethod
    def read(self, results: Iterable[SearchResult]) -> list[ReadDocument]:
        """Return readable text for search results."""


class SnippetReader(PageReader):
    def read(self, results: Iterable[SearchResult]) -> list[ReadDocument]:
        documents: list[ReadDocument] = []
        for result in results:
            documents.append(
                ReadDocument(
                    result=result,
                    text=result.snippet,
                    chunks=[result.snippet],
                    from_page=False,
                    title=result.title,
                    url=result.url,
                    published_at=result.published_at,
                    source_type=result.source_type,
                )
            )
        return documents


class HttpPageReader(PageReader):
    """Fetch simple HTML/text pages and extract readable text.

    This is intentionally conservative and dependency-free. It gives the MVP a
    real reading path without making the core pipeline depend on a crawler.
    """

    def __init__(self, *, timeout: float = 10.0, max_bytes: int = 500_000, opener=urlopen) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._opener = opener

    def read(self, results: Iterable[SearchResult]) -> list[ReadDocument]:
        documents: list[ReadDocument] = []
        for result in results:
            documents.append(self._read_one(result))
        return documents

    def _read_one(self, result: SearchResult) -> ReadDocument:
        if not result.url.startswith(("http://", "https://")):
            return _fallback_document(result)

        request = Request(
            result.url,
            headers={
                "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
                "User-Agent": "websearch-deep-research/0.1",
            },
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read(self.max_bytes)
        except (HTTPError, URLError, TimeoutError, OSError):
            return _fallback_document(result)

        text = _decode_body(body, content_type)
        if "html" in content_type.lower():
            text = _html_to_text(text)
        text = _normalize_text(text)
        if not text:
            return _fallback_document(result)
        return ReadDocument(
            result=result,
            text=text,
            chunks=_chunk_text(text),
            from_page=True,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            source_type=result.source_type,
        )


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = _normalize_text(data)
        if cleaned:
            self.parts.append(cleaned)


def _decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[1].strip()
            break
    return body.decode(charset, errors="replace")


def _html_to_text(html: str) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _fallback_document(result: SearchResult) -> ReadDocument:
    return ReadDocument(
        result=result,
        text=result.snippet,
        chunks=[result.snippet],
        from_page=False,
        title=result.title,
        url=result.url,
        published_at=result.published_at,
        source_type=result.source_type,
    )


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 120) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]
