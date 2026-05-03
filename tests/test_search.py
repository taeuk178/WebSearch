import json
import unittest

from deep_research.models import SearchQuery
from deep_research.policy import RateLimiter
from deep_research.search import ArxivSearchProvider, BraveSearchProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class BraveSearchProviderTest(unittest.TestCase):
    def test_maps_brave_results_to_search_results(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(
                {
                    "web": {
                        "results": [
                            {
                                "title": "Medical Neuroscience Course",
                                "url": "https://example.edu/neuroscience",
                                "description": "A curriculum sequence for medical neuroscience.",
                                "page_age": "2025-01-02",
                            },
                            {
                                "title": "Clinical Neurology Cases",
                                "url": "https://example.org/neurology/cases",
                                "description": "Case-based clinical practice.",
                            },
                        ]
                    }
                }
            )

        provider = BraveSearchProvider("test-key", opener=opener, timeout=3.0)

        results = provider.search([SearchQuery("medical neuroscience", "test")], limit_per_query=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].source_id, "S1")
        self.assertEqual(results[0].source_type, "university_course")
        self.assertEqual(results[0].published_at, "2025-01-02")
        self.assertEqual(results[1].source_id, "S2")
        self.assertEqual(results[1].query, "medical neuroscience")
        self.assertEqual(requests[0][1], 3.0)
        self.assertIn("q=medical+neuroscience", requests[0][0].full_url)
        self.assertEqual(requests[0][0].get_header("X-subscription-token"), "test-key")

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            BraveSearchProvider("")


class ArxivSearchProviderTest(unittest.TestCase):
    def test_maps_arxiv_feed_to_search_results_and_rate_limits_requests(self):
        now = [0.0]
        sleeps = []
        requests = []

        def clock():
            return now[0]

        def sleeper(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        def opener(request, timeout):
            requests.append((request, timeout))
            return BytesResponse(
                b"""<?xml version="1.0" encoding="UTF-8"?>
                <feed xmlns="http://www.w3.org/2005/Atom">
                  <entry>
                    <id>https://arxiv.org/abs/2501.00001</id>
                    <title>Agentic Search Systems</title>
                    <summary>Research on agentic search and evidence workflows.</summary>
                    <published>2025-01-01T00:00:00Z</published>
                    <link href="https://arxiv.org/abs/2501.00001" rel="alternate"/>
                  </entry>
                </feed>"""
            )

        provider = ArxivSearchProvider(
            opener=opener,
            timeout=4.0,
            rate_limiter=RateLimiter(3.5, clock=clock, sleeper=sleeper),
        )

        results = provider.search(
            [SearchQuery("agentic search", "test"), SearchQuery("deep research", "test")],
            limit_per_query=1,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].source_type, "preprint")
        self.assertEqual(results[0].url, "https://arxiv.org/abs/2501.00001")
        self.assertEqual(results[0].published_at, "2025-01-01T00:00:00Z")
        self.assertEqual(sleeps, [3.5])
        self.assertEqual(requests[0][1], 4.0)
        self.assertIn("search_query=all%3Aagentic+search", requests[0][0].full_url)


class BytesResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


if __name__ == "__main__":
    unittest.main()
