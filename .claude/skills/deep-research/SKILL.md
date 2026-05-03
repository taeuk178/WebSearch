---
name: deep-research
description: Run a Perplexity-style deep research pipeline (plan → search → read → rank → synthesize → cite) for any non-trivial information question. Use this whenever the user asks a research-style question that benefits from multi-source synthesis with citations — e.g. "X에 대해 자세히 알아봐줘", "X 논문 정리해줘", "X에 대한 최신 동향이 뭐야", "X 공부하는 방법", "X 비교해줘", "X 리포트 만들어줘". Also use when the user explicitly says "deep research", "딥 리서치", "리서치해줘", or asks for an answer with sources/citations. Prefer this skill over a single web search whenever the question has multiple sub-aspects, requires evidence per claim, or asks for a structured report with sources.
---

# Deep Research

Wraps the `deep_research` Python pipeline (in this repo) so the model can run a full plan → search → read → rank → cite workflow and present a cited answer.

## When to use

Trigger this skill for any of:
- Multi-aspect research questions ("X에 대해 정리해줘", "X 비교", "X 동향")
- Learning roadmaps ("X 공부하는 방법", "X 로드맵")
- Paper / preprint summaries ("X 논문 정리해줘", "arXiv에서 X 찾아줘")
- Any time the user asks for an answer **with citations** or "근거"
- Explicit invocations: "deep research", "딥 리서치", "리서치 돌려줘"

Do **not** use for:
- Simple factual lookups ("파이썬 리스트 컴프리헨션 문법") — direct answer is fine
- Code edits or pure programming tasks
- Conversation about this codebase itself (read the source instead)

## How to invoke

The pipeline is a CLI in this repo at `deep_research.cli`. Run it from the repo root with `--json --output <path>` so the structured bundle is written to disk, then read the bundle.

### Step 1: Pick a search provider

Decide based on signals — do **not** ask the user unless ambiguous:

| Signal | Provider | Flag |
|---|---|---|
| Query mentions "논문", "paper", "preprint", "arxiv" | arxiv | `--search-provider arxiv` |
| `BRAVE_SEARCH_API_KEY` env var is set | brave | `--search-provider brave` |
| Otherwise | mock (development fixtures only) | `--search-provider mock` |

If you fall back to `mock`, **tell the user up front** that results are deterministic fixtures, not real web search, and ask if they want to set `BRAVE_SEARCH_API_KEY` for real results.

To check for the env var: `printenv BRAVE_SEARCH_API_KEY` (empty output = not set).

### Step 2: Decide whether to read full pages

Add `--read-pages` when:
- The user asks for a deep / thorough answer
- The query is technical and snippets won't be enough
- Citations need to quote specifics

Skip `--read-pages` when:
- Quick scan is fine ("간단히 정리")
- arxiv provider already returns abstracts as snippets

### Step 3: Run the pipeline

From the repo root (`/Users/taeuk/Desktop/WebSearch` or wherever the repo is checked out):

```bash
python -m deep_research.cli "<USER_QUERY>" \
  --json \
  --output /tmp/deep_research_bundle.json \
  --search-provider <mock|brave|arxiv> \
  [--read-pages]
```

The CLI also streams stage events to stdout (`planning -> ...`, `searching -> ...`). These are useful progress signals — surface 1–2 short status lines to the user while it runs, but don't dump them all.

### Step 4: Parse the bundle

The JSON bundle at `/tmp/deep_research_bundle.json` matches the schema in `references/bundle_schema.md`. The fields you'll use most:

- `bundle.answer` — the synthesized answer (already references source IDs like `[S1]`, `[S2]`)
- `bundle.ranked_sources[]` — sorted by score; each has `result.source_id`, `result.title`, `result.url`, `result.source_type`, plus `relevance`/`trust`/`freshness`
- `bundle.evidence[]` — claim-level evidence with `source_id`, `outline_section`, `summary`
- `bundle.cautions[]` — safety/rate-limit/quality cautions to surface to the user
- `bundle.limitations[]` — assumptions and constraints the writer made
- `bundle.metadata` — generated_at, safety_risk_level, includes_arxiv

A helper script is available — see "Helper script" below — that runs the pipeline and prints a model-friendly summary.

## How to present the result

The model takes the wrapper's JSON summary and renders it Perplexity-style: **inline numbered links after each sentence/paragraph that came from a source**, then a source list, then cautions, then elapsed time.

### The shape

```
{rewritten answer with inline citation links per sentence/paragraph}

## 출처
[S1] {title} — {url}
[S2] {title} — {url}
...

## 참고 / 주의
- {cautions and limitations, only if non-empty}

---
⏱️ 처리 시간: {elapsed_seconds}초
```

### Inline citation rule (Perplexity-style)

The pipeline's writer outputs `bundle.answer` with citations either inline (`...claim [S3]...`) or in a trailer (`근거 출처: S1, S2`). You should **rewrite the answer** so every claim-bearing sentence or paragraph ends with one or more clickable source links in this exact form:

```
...주장 문장. [[S1]]({url}) [[S2]]({url})
```

That gives Perplexity-like superscript-feeling links: small bracketed source IDs, each one a markdown link to the source URL. Use the `source_url_by_id` map from the wrapper output to fill in the URLs — never write a bare `[S1]` without the link.

How to map sentences to sources:
1. Look at `evidence[]` from the wrapper output — each item has `outline_section`, `claim`, `summary`, and `source_id`.
2. For each sentence/paragraph in the rewritten answer, attach the source IDs whose `claim` or `outline_section` it covers.
3. If a paragraph synthesizes multiple sources, attach all of them: `...설명. [[S1]](url) [[S3]](url) [[S7]](url)`.
4. Plain transitional sentences ("추천 순서는 다음과 같습니다.") get no citation. Only attach citations to substantive claims.
5. If the original answer's trailer says `근거 출처: S1, S14, S2, S4` and you can't confidently map each sentence, attach the full set to the most claim-dense paragraph rather than dropping citations entirely.

### Source list rule

Below the answer, list **only the source IDs actually used inline**. Use the `sources[]` array from the wrapper output (it's already filtered to cited IDs). Order: same order as `sources[]` (by score desc).

### Cautions / limitations

Show the "참고 / 주의" block only if `cautions` or `limitations` is non-empty. Merge both into one bulleted list. Skip generic ones the user already knows (e.g. don't bother re-stating "snippet은 원문보다 신뢰도가 낮음" if you ran with `--read-pages`).

### Elapsed time

Always end with the elapsed-time footer using the wrapper's `elapsed_seconds` value. Format: `⏱️ 처리 시간: 0.42초` (round to 2 decimals; `elapsed_seconds` is already rounded).

This is **pipeline wall-clock time** (subprocess duration: planning → searching → reading → ranking → writing). It does not include your own composition time. That's fine — for the user, the bulk of latency is the pipeline itself.

### Worked example (mock provider, neuroscience query)

Input from wrapper:
```json
{
  "answer": "의료 신경과학은 ... 임상 케이스 순서로 가는 편이 안정적입니다. ... 근거 출처: S1, S14, S2, S4",
  "sources": [{"source_id":"S1","title":"Medical Neuroscience Course Outline","url":"https://example.edu/..."}, ...],
  "source_url_by_id": {"S1":"https://example.edu/medical-neuroscience/course-outline", ...},
  "elapsed_seconds": 0.42
}
```

Final reply you produce:
```markdown
의료 신경과학은 바로 논문이나 임상 질환부터 들어가기보다, 기초 생물학과 생리학을 정리한 뒤 신경해부학, 신경생리학, 시스템 신경과학, 임상 케이스 순서로 가는 편이 안정적입니다. [[S1]](https://example.edu/medical-neuroscience/course-outline) [[S2]](https://example.edu/neuroanatomy/learning-objectives)

추천 순서는 다음과 같습니다.

1. 세포생물학, 일반생리학, 기본 해부학으로 선수지식을 잡습니다. [[S2]](https://example.edu/neuroanatomy/learning-objectives)
2. 뇌, 척수, 말초신경, cranial nerve, 주요 pathway를 신경해부학으로 익힙니다. [[S1]](https://example.edu/medical-neuroscience/course-outline)
3. 활동전위, 시냅스, 감각계, 운동계, 자율신경계를 신경생리학과 시스템 신경과학으로 연결합니다. [[S1]](https://example.edu/medical-neuroscience/course-outline) [[S3]](https://example.com/books/principles-of-neural-science)
4. 마지막에는 stroke, epilepsy, Parkinson disease 같은 임상 케이스로 병변 위치와 증상을 연결해 봅니다. [[S4]](https://example.org/clinical-neurology/cases)

## 출처
- [S1] Medical Neuroscience Course Outline — https://example.edu/medical-neuroscience/course-outline
- [S14] Setting Learning Goals for Neuroscience — https://example.edu/neuroscience/learning-goals
- [S2] Neuroanatomy Learning Objectives for Medical Students — https://example.edu/neuroanatomy/learning-objectives
- [S4] Clinical Neurology Case-Based Learning — https://example.org/clinical-neurology/cases

---
⏱️ 처리 시간: 0.42초
```

### Hard rules

1. **Every claim-bearing sentence/paragraph gets at least one `[[Sn]](url)` link.** No bare `[Sn]`.
2. **The "## 출처" list always comes between the body and the elapsed-time footer.**
3. **Elapsed time is always the very last line of the reply.**
4. **Don't paste the full bundle JSON.** Use only `answer`, `sources`, `evidence`, `source_url_by_id`, `cautions`, `limitations`, `elapsed_seconds`.

## Helper script

`scripts/run_research.py` wraps the CLI and prints a concise JSON summary to stdout (answer + cited sources + cautions only), so you don't have to parse the full bundle yourself. Use it when you want a one-shot invocation:

```bash
python /Users/taeuk/Desktop/WebSearch/.claude/skills/deep-research/scripts/run_research.py \
  "<USER_QUERY>" \
  [--provider mock|brave|arxiv] \
  [--read-pages]
```

It auto-selects the provider using the same rules above (env var → arxiv keyword → mock fallback) when `--provider` is omitted, and writes the full bundle to `/tmp/deep_research_bundle.json` for follow-up inspection if needed.

## Important notes

- **Run from the repo root.** The `deep_research` package needs to be importable. The repo lives at `/Users/taeuk/Desktop/WebSearch` on this machine; if the repo moves, `cd` there before running.
- **arXiv rate limit.** The pipeline enforces a 3.5-second minimum between arXiv requests. A 4-query run can take ~15s+ on arxiv provider. Set expectations with the user before running.
- **Mock provider is for development only.** Its fixtures are hardcoded in `deep_research/search.py` and only respond to specific keywords (neuroscience / AI agents / "learning goals" etc.). For any other query, it returns one generic "Learning Roadmap Template" result. Do not present mock results as real research.
- **Brave API key.** If the user wants to set one, point them to https://brave.com/search/api/ and tell them to `export BRAVE_SEARCH_API_KEY=...` in their shell before invoking.

## References

- `references/bundle_schema.md` — full JSON schema of the research bundle
- `references/providers.md` — details on mock / brave / arxiv providers and when to use each
