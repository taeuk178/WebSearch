import unittest

from deep_research.models import SearchResult
from deep_research.policy import RateLimiter
from deep_research.reader import HttpPageReader, SnippetReader


class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeResponse:
    def __init__(self, body, content_type="text/html; charset=utf-8"):
        self.body = body
        self.headers = FakeHeaders({"Content-Type": content_type})

    def read(self, max_bytes=-1):
        return self.body[:max_bytes]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def make_result(url="https://example.com/page"):
    return SearchResult(
        source_id="S1",
        title="Example",
        url=url,
        snippet="Snippet fallback",
        source_type="web",
        query="example",
    )


class ReaderTest(unittest.TestCase):
    def test_snippet_reader_uses_search_snippet(self):
        document = SnippetReader().read([make_result()])[0]

        self.assertEqual(document.text, "Snippet fallback")
        self.assertFalse(document.from_page)

    def test_http_page_reader_extracts_html_text(self):
        def opener(request, timeout):
            return FakeResponse(b"<html><script>x()</script><body><h1>Title</h1><p>Main text.</p></body></html>")

        document = HttpPageReader(opener=opener, timeout=2.0).read([make_result()])[0]

        self.assertEqual(document.text, "Title Main text.")
        self.assertTrue(document.from_page)

    def test_http_page_reader_falls_back_to_snippet_on_error(self):
        def opener(request, timeout):
            raise OSError("network unavailable")

        document = HttpPageReader(opener=opener).read([make_result()])[0]

        self.assertEqual(document.text, "Snippet fallback")
        self.assertFalse(document.from_page)

    def test_http_page_reader_rate_limits_arxiv_pages(self):
        now = [0.0]
        sleeps = []

        def clock():
            return now[0]

        def sleeper(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        def opener(request, timeout):
            return FakeResponse(b"<html><body><p>arXiv paper text</p></body></html>")

        reader = HttpPageReader(
            opener=opener,
            arxiv_rate_limiter=RateLimiter(3.5, clock=clock, sleeper=sleeper),
        )

        documents = reader.read(
            [
                make_result("https://arxiv.org/abs/2501.00001"),
                make_result("https://arxiv.org/abs/2501.00002"),
            ]
        )

        self.assertEqual(len(documents), 2)
        self.assertTrue(all(document.from_page for document in documents))
        self.assertEqual(sleeps, [3.5])


if __name__ == "__main__":
    unittest.main()
