# Search providers

The pipeline supports three search backends. Pick one with `--search-provider`.

## `mock` (default)

Deterministic local fixtures. Only responds to a small set of keyword families:
- neuroscience / 신경 → returns a curated set about medical neuroscience study
- AI agent / 자동화 → returns AI workflow / risk-checklist fixtures
- "learning goals", "12 week", "3개월" → specific roadmap fixtures
- everything else → one generic "Learning Roadmap Template" result

**Use only for development/testing.** Never present mock results as real research to the user.

## `brave` — Brave Search API

Real web search. Requires:
- `BRAVE_SEARCH_API_KEY` environment variable, OR
- `--brave-api-key <KEY>` flag

Get a key at https://brave.com/search/api/ (free tier available).

Defaults: `country=us`, `search_lang=en`, `timeout=10s`. The pipeline uses `count=4` per query (initial pass) and `count=2` per query (follow-up pass).

Returned `source_type` is inferred from the URL/title (e.g. `.edu` → `university_course`, `nih.gov`/`cdc.gov` → `government_health`, `arxiv.org` → `preprint`).

## `arxiv` — arXiv API

Direct query to `https://export.arxiv.org/api/query`. Returns Atom-formatted preprints.

**Rate limit: minimum 3.5 seconds between requests** (enforced by `RateLimiter`). A typical 4-query initial pass + 3 follow-up queries takes ~25 seconds on arXiv. Tell the user to expect this delay.

Override the interval with `--arxiv-delay <SECONDS>` only if you have a deliberate reason (e.g. you've coordinated with arXiv on a higher rate). Do not lower it casually — arXiv may block the user's IP.

All arxiv results have `source_type=preprint` and a `trust` score of 0.68.

## When to use which

| Situation | Provider |
|---|---|
| User mentions "논문", "paper", "preprint", "arxiv" | `arxiv` |
| Anything else, with `BRAVE_SEARCH_API_KEY` set | `brave` |
| Anything else, no key | `mock` (warn user) |
| Mixed query (papers + general web) | Run twice: `arxiv` first, then `brave`, and combine the answers manually |

## Page reading (`--read-pages`)

Off by default — uses search snippets only. Turn on when:
- Snippets are too short for the question
- Brave provider (snippets are short summaries)
- Quotes / specific numbers matter

Skip when:
- arxiv provider (abstracts already in snippets)
- "간단히" / "quick" requests
- The pipeline run needs to finish fast

`--read-pages` honors the same arXiv 3.5s rate limit when fetching arXiv URLs.
