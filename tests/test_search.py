import json
import unittest

from deep_research.models import SearchQuery
from deep_research.search import BraveSearchProvider


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


if __name__ == "__main__":
    unittest.main()
