from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from .models import StageEvent
from .pipeline import DeepResearchPipeline
from .reader import HttpPageReader, PageReader, SnippetReader
from .search import BraveSearchProvider, MockSearchProvider, SearchProvider, SearchProviderError


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deep research pipeline.")
    parser.add_argument("query", help="User research question")
    parser.add_argument("--json", action="store_true", help="Print the full research bundle as JSON")
    parser.add_argument("--output", type=Path, help="Write the full research bundle to a JSON file")
    parser.add_argument(
        "--search-provider",
        choices=["mock", "brave"],
        default=os.getenv("DEEP_RESEARCH_SEARCH_PROVIDER", "mock"),
        help="Search backend to use. Defaults to mock unless DEEP_RESEARCH_SEARCH_PROVIDER is set.",
    )
    parser.add_argument(
        "--brave-api-key",
        default=os.getenv("BRAVE_SEARCH_API_KEY"),
        help="Brave Search API key. Defaults to BRAVE_SEARCH_API_KEY.",
    )
    parser.add_argument("--search-timeout", type=float, default=10.0, help="Search provider timeout in seconds.")
    parser.add_argument(
        "--read-pages",
        action="store_true",
        help="Fetch result URLs and extract page text. Falls back to snippets when a page cannot be read.",
    )
    parser.add_argument("--read-timeout", type=float, default=10.0, help="Page reader timeout in seconds.")
    args = parser.parse_args()

    events: list[StageEvent] = []

    def on_event(event: StageEvent) -> None:
        events.append(event)
        print(f"{event.stage.value} -> {event.message}")

    try:
        pipeline = DeepResearchPipeline(
            search_provider=_build_search_provider(args),
            page_reader=_build_page_reader(args),
            on_event=on_event,
        )
        bundle = pipeline.run(args.query)
    except (SearchProviderError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")

    payload = asdict(bundle)
    payload["events"] = [asdict(event) for event in events]

    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print()
        print(bundle.answer)


def _build_search_provider(args: argparse.Namespace) -> SearchProvider:
    if args.search_provider == "brave":
        return BraveSearchProvider(api_key=args.brave_api_key, timeout=args.search_timeout)
    return MockSearchProvider()


def _build_page_reader(args: argparse.Namespace) -> PageReader:
    if args.read_pages:
        return HttpPageReader(timeout=args.read_timeout)
    return SnippetReader()


if __name__ == "__main__":
    main()
