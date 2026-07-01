"""
Confidence Engine.

Combines Signal 1 (LLM classifier) and Signal 2 (stylometric heuristics)
into a single final confidence score using the weighted average defined in
planning.md:

    Final Score = (LLM Score × 0.60) + (Stylometric Score × 0.40)

Score interpretation (from planning.md § 2 Uncertainty Representation):
    0.00 – 0.35  →  High-confidence Human
    0.36 – 0.65  →  Uncertain
    0.66 – 1.00  →  High-confidence AI
"""

_LLM_WEIGHT = 0.60
_STYLOMETRIC_WEIGHT = 0.40


def compute_confidence(llm_score: float, stylometric_score: float) -> float:
    """
    Combine both detection signals into a final confidence score.

    Args:
        llm_score:          Float in [0.0, 1.0] from Signal 1 (LLM classifier).
        stylometric_score:  Float in [0.0, 1.0] from Signal 2 (stylometric).

    Returns:
        A float in [0.0, 1.0] representing overall AI likelihood.
        0.0 = Likely Human, 1.0 = Likely AI.
    """
    score = (_LLM_WEIGHT * llm_score) + (_STYLOMETRIC_WEIGHT * stylometric_score)
    return round(max(0.0, min(1.0, score)), 4)
