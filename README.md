# WebSearch Deep Research Prototype

Perplexity-style deep research flow prototype:

```text
queued -> planning -> initial_queries -> searching -> reading -> ranking
-> follow_up_queries -> searching_outline_gaps -> evidence_memory
-> dynamic_outline -> preparing_bundle -> completed
```

## Run

```bash
python -m deep_research.cli "의료 신경과학 공부하는 방법"
```

Full JSON bundle:

```bash
python -m deep_research.cli "의료 신경과학 공부하는 방법" --json
```

Use Brave Search instead of the deterministic mock provider:

```bash
BRAVE_SEARCH_API_KEY=... python -m deep_research.cli "의료 신경과학 공부하는 방법" --search-provider brave
```

You can also set `DEEP_RESEARCH_SEARCH_PROVIDER=brave`.

Use the arXiv API for paper search. arXiv requests are rate-limited to at least 3.5 seconds apart by default:

```bash
python -m deep_research.cli "agentic search 논문 요약" --search-provider arxiv
```

Override the arXiv interval only when you deliberately need a different local policy:

```bash
python -m deep_research.cli "agentic search 논문 요약" --search-provider arxiv --arxiv-delay 3.5
```

Fetch and extract page text instead of using only search snippets:

```bash
BRAVE_SEARCH_API_KEY=... python -m deep_research.cli "의료 신경과학 공부하는 방법" --search-provider brave --read-pages
```

Run the local SSE API and minimal browser UI:

```bash
python -m deep_research.server --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`.

## Architecture

- `deep_research.pipeline.DeepResearchPipeline`: orchestrates the staged workflow.
  It also deduplicates sources by canonical URL and near-duplicate fingerprint before evidence extraction and final ranking.
- `deep_research.reader.PageReader`: replaceable document reading interface.
- `deep_research.reader.SnippetReader`: default reader that uses search snippets.
- `deep_research.reader.HttpPageReader`: optional dependency-free HTML/text reader with snippet fallback and basic chunking.
- `deep_research.writer.AnswerWriter`: replaceable answer composition interface.
- `deep_research.writer.EvidenceAnswerWriter`: deterministic evidence-aware writer that preserves source IDs.
- `deep_research.policy`: execution cautions and rate limiting policy. arXiv API and arXiv page reads use a 3.5-second minimum interval.
- `deep_research.safety.assess_safety`: routes medical risk levels and source quality requirements.
- `deep_research.server`: standard-library SSE endpoint (`POST /research`) and minimal UI (`GET /`).
- `deep_research.search.SearchProvider`: replaceable search interface.
- `deep_research.search.MockSearchProvider`: deterministic local provider for development and tests.
- `deep_research.search.BraveSearchProvider`: optional real search provider using the Brave Search API.
- `deep_research.models`: typed state, source, evidence, and bundle objects.

Additional production search backends can be added by implementing `SearchProvider` for Tavily, Exa, Bing, or a custom crawler. The writer step can also be replaced with an LLM-backed answer composer while preserving the same evidence bundle contract.
