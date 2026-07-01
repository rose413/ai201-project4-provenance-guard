# Provenance Guard

AI-content provenance detection API. Accepts text submissions, runs dual-signal
analysis (LLM semantic classifier + stylometric heuristics), and returns a
structured transparency label backed by a confidence score.

---

## Architecture Overview

The path a submission takes from input to transparency label:

```
POST /submit
     │
     ▼
Rate Limiter (10/min · 100/day per IP)
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
Signal 1: LLM Classifier           Signal 2: Stylometric Analysis
(signals/llm_classifier.py)        (signals/stylometric.py)
  – Sends text to Groq LLM           – Sentence length variance
  – Returns float [0, 1]             – Type-token ratio
                                     – Expressive punctuation density
                                     – Coefficient of variation
                                     – Returns float [0, 1]
     │                                     │
     └──────────────┬──────────────────────┘
                    ▼
          Confidence Engine
          (signals/confidence.py)
          score = (llm × 0.60) + (stylometric × 0.40)
                    │
                    ▼
           Label Generator
           (signals/label_generator.py)
           Maps score → transparency label dict
                    │
                    ▼
            Audit Log (audit.db)
            Persists all fields to SQLite
                    │
                    ▼
           HTTP 200 Response
           { content_id, attribution, confidence, label }
```

**Appeal path:**

```
POST /appeal
     │
     ▼
Retrieve original submission (get_submission)
     │
     ▼
Guard: reject if already under_review (409)
     │
     ▼
update_submission(status="under_review", appeal_reason=…)
     │
     ▼
HTTP 200 Response
```

---

## Detection Signals

### Signal 1 — LLM Classifier (`signals/llm_classifier.py`)

**What it measures:** Semantic plausibility of human authorship. The signal
sends the submitted text to the Groq API (llama-3.1-8b-instant, temperature 0)
with a prompt that instructs the model to score it on a 0.0–1.0 scale. The
prompt directs the model to look for: uniform sentence rhythm with no length
variation, absence of personal voice or idiosyncratic word choice, formulaic
transitions and predictable structure, encyclopedic coverage without personal
perspective, and absence of natural errors or spontaneous digressions.

**Why this signal:** An LLM evaluating LLM output is sensitive to the same
distributional properties that make AI text recognisable to humans — overuse of
hedging phrases, perfect structural balance across paragraphs, absence of the
little inconsistencies that characterise natural writing. A pure rule-based
classifier would need to enumerate these properties manually and would quickly
fall behind model updates. The LLM judge adapts automatically because it was
trained on the same distribution of text it is being asked to detect.

**What it misses:** Non-native speakers who write formally, academics whose
natural register closely mirrors AI output, and writers deliberately mimicking
professional style. The signal has no way to distinguish between "sounds like AI
because AI was trained on formal prose" and "sounds like AI because the author
writes like formal prose." It is also sensitive to topic: highly technical or
encyclopedic content scores higher regardless of authorship. Short texts (fewer
than two sentences) are not meaningful inputs and return a neutral 0.5 fallback.

---

### Signal 2 — Stylometric Analysis (`signals/stylometric.py`)

**What it measures:** Four structural heuristics computed without any external
API call:

| Component | AI-like pole | Human-like pole |
|---|---|---|
| Sentence length variance | Low std dev (uniform) | High std dev (irregular) |
| Type-token ratio (TTR) | Low (repetitive vocab) | High (diverse vocab) |
| Expressive punctuation density | Near zero `!?…` | ≥ 2 % of characters |
| Coefficient of variation (CV) | Low (uniform lengths) | CV ≥ 0.5 |

Each component is normalised to [0, 1] and the four are averaged equally. The
threshold values (std dev ≥ 15 words → human, TTR range 0.3–0.7, punct density
2 %, CV ≥ 0.5) were chosen to place typical AI output near 0.7–0.9 and informal
human writing near 0.1–0.4 based on manual inspection of test samples.

**Why this signal:** Stylometric features are fast, deterministic, and free
from API rate limits. They also provide a check orthogonal to the LLM signal: a
text can fool a semantic judge (e.g. by inserting some personal-sounding
sentences) while still having the uniform sentence length distribution of
generated text. Including both signals reduces the chance that a single
manipulation technique defeats the whole system.

**What it misses:** Academic and legal writing, technical documentation, and
structured reports tend to score high (AI-like) regardless of authorship because
their conventions deliberately enforce uniform sentence structure and formal
vocabulary. A contract or journal abstract will often produce a stylometric
score above 0.6 even when written entirely by a human. The signal also has no
sense of topic or register — it cannot tell the difference between a formally
structured human document and a formally structured AI document.

---

## Confidence Scoring

### Combination approach

```
confidence = (llm_score × 0.60) + (stylometric_score × 0.40)
```

The LLM classifier carries the larger weight (60 %) because it evaluates
semantic properties that are harder to spoof: the presence of personal voice,
idiosyncratic reasoning, and spontaneous digressions. The stylometric signal
carries 40 % because it is fast and orthogonal but easier to game — a few
exclamation marks and deliberately varied sentence lengths can shift it toward
the human end of the scale without actually making the content more human.

The final score is clamped to [0, 1] and rounded to four decimal places.

### Validation approach

Validation was done by running the combined score against the same three text
samples used in `test_classifier.py` and `test_stylometric.py` (informal human
writing, encyclopedic AI output, and a deliberately mixed sample) and confirming
the combined score placed each sample in the expected zone. The label generator
tests (`test_label_generator.py`) then verified that every zone boundary is
reachable and produces the correct label text, using mocked signal values that
force the confidence into each of the three zones.

### Two example submissions with different confidence scores

The texts below are excerpts of the full submissions. The stylometric scores
were computed from the complete submitted text; running the analysis on the
truncated excerpt alone will produce different values.

**High-confidence case — encyclopedic AI text**

> *"Machine learning is a subset of artificial intelligence that enables systems
> to learn and improve from experience without being explicitly programmed. It
> focuses on developing computer programs that can access data and use it to
> learn for themselves..."*

```json
{
  "llm_score": 0.8,
  "stylometric_score": 0.6283,
  "confidence": 0.7313,
  "label": { "origin": "Likely AI-Generated" }
}
```

Both signals agree. The LLM classifier scores it 0.80 (encyclopedic register,
no personal voice). The stylometric signal scores it 0.63 (low sentence variance,
low expressive punctuation). The weighted combination produces 0.73, well above
the 0.66 threshold.

---

**Lower-confidence case — informal personal writing**

> *"ok so i completely blanked on my exam today lol. spent three hours studying
> last night and the ONE section i skipped was literally half the test..."*

```json
{
  "llm_score": 0.2,
  "stylometric_score": 0.3918,
  "confidence": 0.2767,
  "label": { "origin": "Likely Human-Authored" }
}
```

The LLM classifier scores it 0.20 — the casual register, abbreviations (lol),
and self-deprecating tone are strong human-authorship signals. The stylometric
score is higher (0.39) because the short, fragmented sentences happen to produce
low variance — but it is outweighed by the LLM component. Combined score of
0.28 sits in the high-confidence human zone.

The gap between these two cases (0.73 vs 0.28) demonstrates that the scoring
produces meaningful variation across clearly different content types.

---

## Transparency Labels

All three variants, with the exact text each one displays:

### High-confidence AI (confidence ≥ 0.66)

> **Content Origin:** Likely AI-Generated
>
> Our system detected strong structural and semantic patterns commonly associated
> with AI-generated text.

### Uncertain (0.36 ≤ confidence ≤ 0.65)

> **Content Origin:** Unverified
>
> This text contains a mixture of characteristics, and the system cannot
> confidently determine its origin.

### High-confidence Human (confidence ≤ 0.35)

> **Content Origin:** Likely Human-Authored
>
> Our system detected high linguistic variation and natural writing patterns.

The `label` field in every `/submit` response is a JSON object:

```json
{
  "origin":  "<one of the three titles above>",
  "message": "<the explanatory sentence above>"
}
```

The plain-text `origin` string is also stored in the `attribution` column of the
audit log so reviewers can see the classification without parsing the full
response again.

---

## Rate Limiting

Rate limiting is applied to `POST /submit` only. Read (`GET /log`) and appeal
(`POST /appeal`) endpoints are not throttled.

### Chosen limits

```
10 requests per minute
100 requests per day
(per IP address)
```

### Reasoning

**10 per minute** — A human writer revising and re-submitting a document would
rarely exceed 10 submissions in a single minute even during an active editing
session. Ten per minute allows natural bursts (pasting several drafts in quick
succession) while making automated flooding impractical: a script sending
hundreds of requests per minute is blocked after the first ten.

**100 per day** — A productive creator might legitimately check many different
pieces of work throughout a day: different articles, chapters, or student
assignments. 100 per day is generous enough to cover real-world power users
while keeping the Groq API bill bounded. An automated scraper targeting the
endpoint at scale would hit this ceiling well before causing meaningful cost or
availability impact.

**No blanket default** — Only `/submit` is expensive (it makes an external LLM
API call on every request). `/log` and `/appeal` are cheap SQLite operations and
do not need per-IP throttling at this stage.

### Evidence — rate limit in action

The following output was captured by sending 12 rapid POST requests to `/submit`
against the running server. Requests 1–10 return `200`; requests 11–12 are
rejected with `429 Too Many Requests`.

```
200
200
200
200
200
200
200
200
200
200
429
429
```

Test command used:

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    --data-raw '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

---

## Audit Log

Every submission is persisted to `audit.db` (SQLite). The `GET /log` endpoint
returns the 20 most recent entries as structured JSON.

### Fields

| Field | Type | Set by | Description |
|---|---|---|---|
| `content_id` | string (UUID) | `/submit` | Unique identifier for the submission |
| `timestamp` | string (ISO-8601 UTC) | `/submit` | When the submission was received |
| `creator_id` | string | `/submit` | Identifier supplied by the submitter |
| `llm_score` | float [0, 1] | Signal 1 | LLM semantic classifier score |
| `stylometric_score` | float [0, 1] | Signal 2 | Stylometric heuristic score |
| `confidence` | float [0, 1] | Confidence Engine | Weighted combination (60 % LLM + 40 % stylometric) |
| `attribution` | string | Label Generator | Plain-text origin classification stored in the DB |
| `status` | string | `/submit` → `/appeal` | `"classified"` or `"under_review"` |
| `appeal_reason` | string \| null | `/appeal` | Creator's written reasoning; null until an appeal is filed |

### Sample entries (3 real submissions)

The three entries below cover all three transparency label variants. Entry 2
also shows a filed appeal.

```json
{
  "entries": [
    {
      "content_id": "6327b9f0-7f57-4197-a39f-2eafaddd5af0",
      "timestamp": "2026-06-30T17:28:59.313Z",
      "creator_id": "creator_mixed",
      "llm_score": 0.2,
      "stylometric_score": 0.6529,
      "confidence": 0.3812,
      "attribution": "Unverified",
      "status": "classified",
      "appeal_reason": null
    },
    {
      "content_id": "11d5c7d7-7fd3-4ca1-9102-540a53663e8f",
      "timestamp": "2026-06-30T17:28:50.611Z",
      "creator_id": "creator_ai",
      "llm_score": 0.8,
      "stylometric_score": 0.6283,
      "confidence": 0.7313,
      "attribution": "Likely AI-Generated",
      "status": "under_review",
      "appeal_reason": "I wrote this passage myself as a study guide summary after reading several textbooks. I am a computer science student and tend to write in a formal, structured style when explaining technical concepts."
    },
    {
      "content_id": "49a290f2-49cc-41c7-af0b-c9e7edbf0535",
      "timestamp": "2026-06-30T17:28:40.708Z",
      "creator_id": "creator_human",
      "llm_score": 0.2,
      "stylometric_score": 0.3918,
      "confidence": 0.2767,
      "attribution": "Likely Human-Authored",
      "status": "classified",
      "appeal_reason": null
    }
  ]
}
```

---

## Known Limitations

### Academic and technical writing is systematically misclassified

The most predictable failure mode is formal human writing that follows genre
conventions. Academic abstracts, legal clauses, technical documentation, and
instructional prose are written with uniform sentence structure, precise
vocabulary, minimal expressive punctuation, and deliberate avoidance of personal
voice — exactly the stylistic profile the system associates with AI output.

This is not a data quality problem that more training would fix. It is a
property of the signals themselves: the stylometric signal measures structural
uniformity, and formal human genres are deliberately uniform. The LLM classifier
reinforces the error because it was trained on text where this register is
disproportionately represented in AI output.

In practice, a PhD student submitting their dissertation introduction, a lawyer
submitting a contract clause, or a technical writer submitting API documentation
would all receive an "Unverified" or "Likely AI-Generated" verdict regardless of
whether AI was involved. The system would need either a genre-detection
pre-filter (to apply different thresholds for identified formal text types) or
signal calibration data drawn from verified human samples in those genres before
it could be used reliably in academic or professional settings.

---

## Spec Reflection

**One way the spec helped:** The explicit threshold table in planning.md (0.00–0.35
human / 0.36–0.65 uncertain / 0.66–1.00 AI) eliminated the largest design
decision in the label generator. Without that table, choosing where to draw
the boundaries would have required calibration experiments. Having the numbers
specified meant the implementation could go directly from a working confidence
score to a working label with no additional iteration.

**One way implementation diverged from the spec:** The spec's appeal eligibility
section says "only the authenticated creator who originally submitted the content
may file an appeal" and describes a `creator_id` match as the verification
mechanism. The initial implementation added `creator_id` as a required field on
`POST /appeal` to enforce this. However, the spec's own example curl command
only includes `content_id` and `creator_reasoning` — there is no `creator_id`
in the request body, and no session or token-based authentication exists in the
API as designed. Requiring a field that any caller could set to any value does
not actually provide the access control the spec describes; it just adds a
required parameter with no real enforcement. The implementation was simplified to
match the two-field interface the spec example shows, with the understanding that
real creator verification would require a proper authentication layer (session
tokens, JWT, or similar) that is outside the scope of this project.

---

## AI Usage

### Instance 1 — Label generator and test suite

**Directed:** Generate a `generate_label(confidence)` function in
`signals/label_generator.py` that maps the three confidence zones from
planning.md to label dicts, and write a test script that verifies all three
variants are reachable both by calling the function directly and by hitting
`POST /submit` through the Flask test client.

**Produced:** The label generator with three module-level label dicts and a
single function using two threshold comparisons. The test script (`test_label_generator.py`)
used `unittest.mock.patch` to stub `classify_with_llm` and `analyze_stylometry`
so the confidence was deterministic without real API calls.

**Revised:** The test script's endpoint section patched at the `app` module
level (`app.classify_with_llm`, `app.analyze_stylometry`) rather than at the
signals module level. The initial draft patched the signals modules directly,
which does not intercept the already-imported names in `app.py`. This was
identified during the test run and corrected before the tests were finalised.

---

### Instance 2 — POST /appeal endpoint

**Directed:** Build `POST /appeal` following the appeal flow diagram in
planning.md: retrieve the original submission, guard against duplicate appeals,
update status to `"under_review"`, write the creator's reasoning to the audit
log, return a confirmation.

**Produced:** The full endpoint including a `creator_id` field and a 403
response that rejected appeals from anyone other than the original submitter.

**Revised/overridden:** The `creator_id` requirement was removed after comparing
the endpoint's interface against the spec's own example curl command, which only
sends `content_id` and `creator_reasoning`. The 403 branch was dropped because
a `creator_id` field that any caller can set to any string string provides no
real access control — it would reject honest callers while doing nothing to stop
a bad actor who simply copies the original `creator_id` from the `GET /log`
response. The trade-off (simpler interface, honest about what it cannot enforce)
was preferred over the false security of a field that looks like authentication
but is not.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/submit` | Analyse text and receive a provenance label |
| `POST` | `/appeal` | File an appeal against a classification decision |
| `GET` | `/log` | Retrieve the 20 most recent audit log entries |

### POST /submit

Request:
```json
{ "text": "<content to analyse>", "creator_id": "<user identifier>" }
```

Response:
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "attribution": { "llm_score": 0.75, "stylometric_score": 0.68 },
  "confidence": 0.7176,
  "label": {
    "origin": "Likely AI-Generated",
    "message": "Our system detected strong structural and semantic patterns commonly associated with AI-generated text."
  }
}
```

### POST /appeal

Request:
```json
{ "content_id": "<UUID>", "creator_reasoning": "<written explanation>" }
```

Response:
```json
{
  "message": "Appeal received. Your content has been flagged for human review.",
  "content_id": "550e8400-...",
  "status": "under_review"
}
```

---

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
python app.py
```