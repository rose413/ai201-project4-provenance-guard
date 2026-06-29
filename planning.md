# Provenance Guard – Project Planning

## 1. Detection Signals

To ensure robust detection and minimize blind spots, the system uses a multi-signal pipeline that combines semantic and structural analysis.

### Signal 1: LLM Classifier (Semantic)

**Purpose**

* Measures semantic meaning, context, and tone.
* Produces a holistic judgment of the text.

**Why It Matters**

* AI models recognize nuanced writing patterns and common AI-generated structures.

**Limitations**

* Does not analyze statistical writing structure.
* Can be influenced by prompt engineering or framing.

**Output**

* Float score between `0.0` (Likely Human) and `1.0` (Likely AI).

---

### Signal 2: Stylometric Heuristics (Structural)

**Purpose**

* Measures statistical writing characteristics such as:

  * Sentence length variance
  * Type-token ratio (lexical diversity)
  * Punctuation density
  * Writing consistency

**Why It Matters**

* AI-generated text tends to be more uniform and repetitive.
* Human writing generally shows greater variation and expressive punctuation.

**Limitations**

* Cannot understand semantic meaning.
* Writing styles vary naturally across individuals.

**Output**

* Float score between `0.0` (Likely Human) and `1.0` (Likely AI).

---

### Confidence Engine

The final confidence score combines both signals using a weighted average.

```text
Final Score = (LLM Score × 0.60) + (Stylometric Score × 0.40)
```

The higher weight is assigned to the LLM classifier while allowing stylometric analysis to influence uncertain cases.

---

## 2. Uncertainty Representation

The final confidence score represents the likelihood that the submitted text is AI-generated.

| Score Range | Classification        |
| ----------- | --------------------- |
| 0.00 – 0.35 | High-confidence Human |
| 0.36 – 0.65 | Uncertain             |
| 0.66 – 1.00 | High-confidence AI    |

### Example

A score of **0.60** indicates that the system detected some AI-like characteristics while also finding enough human variation that it cannot make a confident determination.

This falls into the **Uncertain** category.

---

## 3. Transparency Labels

The numerical confidence score is converted into a user-friendly label.

### High-confidence AI

> **Content Origin:** Likely AI-Generated
> Our system detected strong structural and semantic patterns commonly associated with AI-generated text.

---

### High-confidence Human

> **Content Origin:** Likely Human-Authored
> Our system detected high linguistic variation and natural writing patterns.

---

### Uncertain

> **Content Origin:** Unverified
> This text contains a mixture of characteristics, and the system cannot confidently determine its origin.

---

## 4. Appeals Workflow

### Eligibility

Only the authenticated creator who originally submitted the content may file an appeal.

### Appeal Submission

The creator provides:

* Written explanation
* Optional links to drafts or revision history
* Description of their writing process

### System Actions

Upon receiving an appeal:

1. Retrieve the original submission.
2. Update the content status to **Under Review**.
3. Record the appeal reason in the Audit Log.
4. Associate the appeal with the original submission ID.

### Reviewer Dashboard

Human moderators are presented with:

* Original submitted text
* Final confidence score
* LLM classifier score
* Stylometric score
* Transparency label
* Creator's appeal statement

---

## 5. Anticipated Edge Cases

### Edge Case 1 – Non-Native English Writers

Potential Issue:

* Smaller vocabulary
* Simpler sentence structures
* Lower type-token ratio

Possible Impact:

* Stylometric analysis may incorrectly interpret these characteristics as AI-generated writing.

---

### Edge Case 2 – Academic or Technical Writing

Potential Issue:

* Formal tone
* Predictable sentence structure
* Specialized vocabulary

Possible Impact:

* The semantic classifier may incorrectly classify highly structured technical writing as AI-generated.

---

# System Architecture

## Submission Flow

```text
POST /submit
        │
        ▼
Rate Limiter
        │
        ▼
────────────────────────────────────────────
│                                          │
▼                                          ▼
LLM Classifier                    Stylometric Analysis
│                                          │
───────────────┬───────────────────────────
               ▼
       Confidence Engine
               │
               ▼
      Label Generator
               │
               ▼
         Audit Log
               │
               ▼
        HTTP 200 Response
```

---

## Appeal Flow

```text
POST /appeal
        │
        ▼
Retrieve Original Decision
        │
        ▼
Update Status → Under Review
        │
        ▼
Record Appeal in Audit Log
        │
        ▼
HTTP 200 Response
```

---

# AI Development Plan

## Milestone 3 — Submission Endpoint & First Signal

### Context Provided

* Detection Signals
* System Architecture

### Prompt

> Generate a Flask application skeleton with a rate-limited `POST /submit` endpoint and implement the LLM classifier signal function.

### Verification

* Send sample requests using Postman or `curl`.
* Confirm:

  * HTTP 200 response
  * Valid score between `0.0` and `1.0`
  * Endpoint processes submitted text successfully

---

## Milestone 4 — Stylometric Analysis & Confidence Engine

### Context Provided

* Detection Signals
* Uncertainty Representation
* Architecture

### Prompt

> Generate the stylometric analysis function and implement the confidence engine that combines both signals using the defined weighted average and thresholds.

### Verification

Test with:

* Casual human-written journal entries
* Clearly AI-generated passages

Expected outcome:

* Human writing scores in the Human range
* AI-generated text scores in the AI range
* Mixed cases fall into the Uncertain category

---

## Milestone 5 — Production Features

### Context Provided

* Transparency Labels
* Appeals Workflow
* Architecture

### Prompt

> Implement the transparency label generation logic and create the `POST /appeal` endpoint that updates submission status and records the appeal in the audit log.

### Verification

* Test all three confidence thresholds.
* Confirm correct label generation.
* Submit an appeal.
* Verify:

  * Status changes to **Under Review**
  * Appeal is recorded in the Audit Log
  * Original submission remains linked to the appeal
