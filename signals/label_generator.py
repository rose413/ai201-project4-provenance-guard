"""
Label Generator — converts a numerical confidence score into a transparency label.

Score thresholds (from planning.md):
    0.66 – 1.00  →  High-confidence AI
    0.36 – 0.65  →  Uncertain
    0.00 – 0.35  →  High-confidence Human

Each label is a dict with two keys:
    origin   – short classification shown to users ("Likely AI-Generated", etc.)
    message  – one-sentence explanation of the decision
"""

_HIGH_AI_THRESHOLD = 0.66
_HIGH_HUMAN_THRESHOLD = 0.35

_LABEL_AI = {
    "origin": "Likely AI-Generated",
    "message": (
        "Our system detected strong structural and semantic patterns "
        "commonly associated with AI-generated text."
    ),
}

_LABEL_HUMAN = {
    "origin": "Likely Human-Authored",
    "message": (
        "Our system detected high linguistic variation and natural writing patterns."
    ),
}

_LABEL_UNCERTAIN = {
    "origin": "Unverified",
    "message": (
        "This text contains a mixture of characteristics, and the system cannot "
        "confidently determine its origin."
    ),
}


def generate_label(confidence: float) -> dict:
    """
    Map a confidence score to a transparency label dict.

    Args:
        confidence: Float in [0.0, 1.0] from the Confidence Engine.
                    Values closer to 1.0 indicate AI-generated content.

    Returns:
        Dict with keys ``origin`` (str) and ``message`` (str).
    """
    if confidence >= _HIGH_AI_THRESHOLD:
        return _LABEL_AI
    if confidence <= _HIGH_HUMAN_THRESHOLD:
        return _LABEL_HUMAN
    return _LABEL_UNCERTAIN
