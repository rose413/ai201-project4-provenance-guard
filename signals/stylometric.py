"""
Signal 2 — Stylometric Heuristics (Structural).

Measures statistical writing characteristics to estimate AI-likelihood:
  - Sentence length variance
  - Type-token ratio (lexical diversity)
  - Punctuation density (expressive punctuation)
  - Writing consistency (coefficient of variation)
"""

import re
import math


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence-ending punctuation followed by whitespace or EOS."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in parts if s.strip()]


def _tokenize_words(text: str) -> list[str]:
    """Return alphabetic word tokens only (strips punctuation)."""
    return re.findall(r'\b[a-zA-Z]+\b', text)


def analyze_stylometry(text: str) -> float:
    """
    Signal 2 — Stylometric Heuristics (Structural).

    Analyzes four structural writing characteristics and combines them into a
    single AI-likelihood score.

    Scoring intuition (per characteristic):
        Uniform sentence lengths     → AI-like  (variance_ai_score  → 1.0)
        Low lexical diversity (TTR)  → AI-like  (ttr_ai_score       → 1.0)
        Sparse expressive punct.     → AI-like  (punct_ai_score     → 1.0)
        Uniform sentence structure   → AI-like  (consistency_score  → 1.0)

    Args:
        text: The content to evaluate.

    Returns:
        A float in [0.0, 1.0] where 0.0 is Likely Human and 1.0 is Likely AI.
        Returns 0.5 (neutral) when the text is too short to analyze reliably.
    """
    sentences = _split_sentences(text)
    words = _tokenize_words(text)

    # Require at least 2 sentences and 10 words for a meaningful analysis
    if len(sentences) < 2 or len(words) < 10:
        return 0.5

    # ------------------------------------------------------------------
    # Component 1 — Sentence length variance
    # AI text tends to produce uniform sentence lengths (low std dev).
    # Threshold: std dev ≥ 15 words  →  "definitely human"  →  score 0.0
    # ------------------------------------------------------------------
    sent_lengths = [len(_tokenize_words(s)) for s in sentences]
    mean_len = sum(sent_lengths) / len(sent_lengths)
    std_dev = math.sqrt(
        sum((l - mean_len) ** 2 for l in sent_lengths) / len(sent_lengths)
    )
    variance_ai_score = max(0.0, 1.0 - min(std_dev, 15.0) / 15.0)

    # ------------------------------------------------------------------
    # Component 2 — Type-token ratio (lexical diversity)
    # Low TTR = repetitive vocabulary = AI-like.
    # Map TTR from [0.3 (AI) → 0.7 (human)] linearly to [1.0 → 0.0].
    # ------------------------------------------------------------------
    lower_words = [w.lower() for w in words]
    ttr = len(set(lower_words)) / len(lower_words)
    ttr_ai_score = max(0.0, min(1.0, (0.7 - ttr) / 0.4))

    # ------------------------------------------------------------------
    # Component 3 — Expressive punctuation density
    # Human writing uses more !  ?  ...  and em-dashes for expressiveness.
    # Threshold: 2 % density  →  "definitely human"  →  score 0.0
    # ------------------------------------------------------------------
    expressive_count = (
        sum(1 for c in text if c in "!?")
        + text.count("...")
        + text.count("\u2026")   # Unicode ellipsis '…'
    )
    punct_density = expressive_count / max(len(text), 1)
    punct_ai_score = max(0.0, 1.0 - min(punct_density / 0.02, 1.0))

    # ------------------------------------------------------------------
    # Component 4 — Writing consistency (coefficient of variation)
    # Low CV = sentences are all the same length = AI-like.
    # Threshold: CV ≥ 0.5  →  "definitely human"  →  score 0.0
    # ------------------------------------------------------------------
    cv = std_dev / mean_len if mean_len > 0 else 0.0
    consistency_ai_score = max(0.0, 1.0 - min(cv / 0.5, 1.0))

    # Equal-weight combination of all four components
    stylometric_score = (
        variance_ai_score
        + ttr_ai_score
        + punct_ai_score
        + consistency_ai_score
    ) / 4.0

    return round(stylometric_score, 4)
