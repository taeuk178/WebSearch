#!/usr/bin/env python3
"""Wrapper around `python -m deep_research.cli` for skill use.

Picks a sensible search provider, runs the pipeline, parses the bundle,
and prints a model-friendly JSON summary to stdout (answer + cited
sources + cautions). The full bundle is written to /tmp/deep_research_bundle.json
for follow-up inspection.

Usage:
    run_research.py "<query>" [--provider mock|brave|arxiv] [--read-pages]
                              [--repo-root <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_REPO_ROOT = Path("/Users/taeuk/Desktop/WebSearch")
BUNDLE_PATH = Path("/tmp/deep_research_bundle.json")
ARXIV_KEYWORDS = ("arxiv", "preprint", "paper", "papers", "논문", "프리프린트")


def pick_provider(query: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    lower = query.lower()
    if any(keyword in lower for keyword in ARXIV_KEYWORDS):
        return "arxiv"
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        return "brave"
    return "mock"


def run_pipeline(query: str, provider: str, read_pages: bool, repo_root: Path) -> tuple[dict, float]:
    cmd = [
        sys.executable,
        "-m",
        "deep_research.cli",
        query,
        "--json",
        "--output",
        str(BUNDLE_PATH),
        "--search-provider",
        provider,
    ]
    if read_pages:
        cmd.append("--read-pages")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(repo_root))

    start = time.monotonic()
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - start

    if result.returncode != 0:
        raise RuntimeError(
            f"deep_research.cli failed (exit {result.returncode}):\n"
            f"stderr: {result.stderr.strip()}\n"
            f"stdout tail: {result.stdout.strip()[-400:]}"
        )

    if not BUNDLE_PATH.exists():
        raise RuntimeError("Pipeline ran but no bundle was written to /tmp/deep_research_bundle.json.")

    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8")), elapsed


def cited_source_ids(answer: str) -> list[str]:
    # The writer emits two citation styles, depending on domain/version:
    #   inline:  "...something [S3]..."
    #   trailer: "근거 출처: S1, S14, S2, S4"
    # Both should round-trip to the source list.
    ids = re.findall(r"\[(S\d+)\]", answer)
    ids += re.findall(r"\bS\d+\b", answer)
    return list(dict.fromkeys(ids))


def summarize(bundle: dict, provider: str, elapsed_seconds: float) -> dict:
    answer = bundle.get("answer", "")
    ranked = bundle.get("ranked_sources", []) or []
    evidence = bundle.get("evidence", []) or []

    by_id = {item["result"]["source_id"]: item for item in ranked}
    cited = cited_source_ids(answer)

    if cited:
        chosen = [by_id[sid] for sid in cited if sid in by_id]
    else:
        chosen = ranked[:5]

    sources = [
        {
            "source_id": item["result"]["source_id"],
            "title": item["result"]["title"],
            "url": item["result"]["url"],
            "source_type": item["result"]["source_type"],
            "score": round(
                item["relevance"] * 0.5 + item["trust"] * 0.35 + item["freshness"] * 0.15,
                3,
            ),
        }
        for item in chosen
    ]

    # Lookup map so the model can resolve [Sn] -> URL when inserting Perplexity-style links.
    source_url_by_id = {item["result"]["source_id"]: item["result"]["url"] for item in ranked}
    source_title_by_id = {item["result"]["source_id"]: item["result"]["title"] for item in ranked}

    # Trim evidence to the fields the model actually needs to map sentences -> citations.
    trimmed_evidence = [
        {
            "source_id": e["source_id"],
            "outline_section": e["outline_section"],
            "claim": e["claim"],
            "summary": e["summary"],
        }
        for e in evidence
    ]

    return {
        "provider": provider,
        "question": bundle.get("question", {}).get("normalized", ""),
        "answer": answer,
        "sources": sources,
        "evidence": trimmed_evidence,
        "source_url_by_id": source_url_by_id,
        "source_title_by_id": source_title_by_id,
        "cautions": bundle.get("cautions", []) or [],
        "limitations": bundle.get("limitations", []) or [],
        "metadata": bundle.get("metadata", {}) or {},
        "elapsed_seconds": round(elapsed_seconds, 2),
        "bundle_path": str(BUNDLE_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deep_research pipeline and print a concise summary.")
    parser.add_argument("query")
    parser.add_argument("--provider", choices=["mock", "brave", "arxiv"], default=None)
    parser.add_argument("--read-pages", action="store_true")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(os.getenv("DEEP_RESEARCH_REPO_ROOT", str(DEFAULT_REPO_ROOT))),
    )
    args = parser.parse_args()

    if not (args.repo_root / "deep_research" / "cli.py").exists():
        sys.exit(
            f"error: deep_research package not found under {args.repo_root}. "
            "Set --repo-root or DEEP_RESEARCH_REPO_ROOT to the repo containing the deep_research/ package."
        )

    provider = pick_provider(args.query, args.provider)
    if provider == "mock":
        print(
            "[run_research] WARNING: using mock provider. Results are hardcoded fixtures, "
            "not real web search. Set BRAVE_SEARCH_API_KEY or pass --provider arxiv for real results.",
            file=sys.stderr,
        )

    bundle, elapsed = run_pipeline(args.query, provider, args.read_pages, args.repo_root)
    summary = summarize(bundle, provider, elapsed)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
