# Research bundle schema

The CLI writes a JSON object with this shape (from `deep_research/models.py`).

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `question` | object | Normalized question metadata |
| `plan` | object | Subquestions, outline, assumptions |
| `initial_queries` | array | Queries used in the first search pass |
| `follow_up_queries` | array | Queries used to fill outline gaps |
| `ranked_sources` | array | Sorted by score desc; this is what to cite |
| `evidence` | array | Per-claim evidence tied to source IDs |
| `final_outline` | array of strings | The outline used by the writer |
| `answer` | string | Synthesized answer; embeds `[S\d+]` source IDs |
| `limitations` | array of strings | Assumptions and constraints |
| `cautions` | array of strings | Safety / rate-limit / quality cautions |
| `metadata` | object | `generated_at`, `safety_risk_level`, `includes_arxiv` |
| `events` | array | Stage events (only present when run via CLI) |

## `question` object

```json
{
  "raw": "원본 질문 그대로",
  "normalized": "공백 정리된 질문",
  "intent": "learning_plan | research_answer",
  "domain": "medical_neuroscience | general",
  "risk_level": "low | medium | high",
  "output_format": "roadmap | briefing",
  "language": "ko"
}
```

## `plan` object

```json
{
  "main_question": "...",
  "subquestions": ["...", "..."],
  "outline": ["섹션1", "섹션2", "..."],
  "assumptions": ["..."]
}
```

## `ranked_sources[]`

```json
{
  "result": {
    "source_id": "S1",
    "title": "...",
    "url": "https://...",
    "snippet": "...",
    "source_type": "university_course | textbook | medical_education | preprint | government_health | technology | business | education | web",
    "query": "검색어",
    "published_at": "2024" | null
  },
  "relevance": 0.95,
  "trust": 0.95,
  "freshness": 0.92
}
```

The composite score is `relevance*0.5 + trust*0.35 + freshness*0.15`. Sources are pre-sorted by it.

## `evidence[]`

```json
{
  "source_id": "S3",
  "claim": "한 줄 주장",
  "summary": "근거 요약 (~420자)",
  "confidence": 0.86,
  "outline_section": "선수지식",
  "chunk_index": 0
}
```

## `metadata`

```json
{
  "generated_at": "2026-05-04T...Z",
  "safety_risk_level": "low | medium | high",
  "includes_arxiv": true | false
}
```

## Citation conventions

- `bundle.answer` already contains `[S1]`, `[S2]`-style references inline (when the writer added them).
- The `source_id` strings in `ranked_sources[].result.source_id` and `evidence[].source_id` are the same namespace — safe to join.
- IDs are assigned in search-result order, not score order, so don't assume `S1` is the top-ranked source.
