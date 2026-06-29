"""
Standalone test for Signal 2: Stylometric Heuristics.

Run before wiring into the endpoint:
    python test_stylometric.py

Prints each raw metric alongside the final stylometric score, then
compares Signal 2 with Signal 1 (LLM classifier) on the same three
samples used in test_classifier.py so you can see where they agree
and where they diverge.

Expected orientation:
    HUMAN text  → stylometric score near 0.00 – 0.35
    AI text     → stylometric score near 0.66 – 1.00
    MIXED text  → score anywhere (uncertain is fine)
"""

import math
from dotenv import load_dotenv

load_dotenv()

from signals.stylometric import analyze_stylometry, _split_sentences, _tokenize_words
from signals.llm_classifier import classify_with_llm
from signals.confidence import compute_confidence

# Same three samples used in test_classifier.py
SAMPLES = [
    (
        "HUMAN",
        "ugh i totally bombed that presentation today lol. my hands were shaking "
        "the whole time and i kept losing my place. at least my prof seemed chill "
        "about it tho. gonna take a nap and pretend it didn't happen",
    ),
    (
        "AI",
        "Artificial intelligence refers to the simulation of human intelligence "
        "processes by computer systems. These processes include learning, reasoning, "
        "and self-correction. AI applications include expert systems, natural language "
        "processing, and machine vision. The field continues to evolve rapidly, with "
        "significant implications for various industries.",
    ),
    (
        "MIXED",
        "I've been thinking a lot about climate change lately. The scientific consensus "
        "is clear: global temperatures have risen approximately 1.1 degrees Celsius "
        "since pre-industrial times. But honestly it's just scary to think about, "
        "you know? Like what does that actually mean for my kids?",
    ),
]


def label_from_score(score: float) -> str:
    if score <= 0.35:
        return "High-confidence Human"
    if score <= 0.65:
        return "Uncertain"
    return "High-confidence AI"


def raw_metrics(text: str) -> dict:
    """
    Compute and return each individual stylometric metric so they can be
    inspected before the final weighted combination.
    """
    sentences = _split_sentences(text)
    words = _tokenize_words(text)

    if len(sentences) < 2 or len(words) < 10:
        return {"note": "text too short — neutral score (0.5) returned"}

    # Sentence length variance
    sent_lengths = [len(_tokenize_words(s)) for s in sentences]
    mean_len = sum(sent_lengths) / len(sent_lengths)
    std_dev = math.sqrt(
        sum((l - mean_len) ** 2 for l in sent_lengths) / len(sent_lengths)
    )
    variance_ai_score = max(0.0, 1.0 - min(std_dev, 15.0) / 15.0)

    # Type-token ratio
    lower_words = [w.lower() for w in words]
    ttr = len(set(lower_words)) / len(lower_words)
    ttr_ai_score = max(0.0, min(1.0, (0.7 - ttr) / 0.4))

    # Expressive punctuation density
    expressive_count = (
        sum(1 for c in text if c in "!?")
        + text.count("...")
        + text.count("\u2026")
    )
    punct_density = expressive_count / max(len(text), 1)
    punct_ai_score = max(0.0, 1.0 - min(punct_density / 0.02, 1.0))

    # Coefficient of variation
    cv = std_dev / mean_len if mean_len > 0 else 0.0
    consistency_ai_score = max(0.0, 1.0 - min(cv / 0.5, 1.0))

    return {
        "num_sentences":       len(sentences),
        "num_words":           len(words),
        "sent_lengths":        sent_lengths,
        "mean_sent_len":       round(mean_len, 2),
        "std_dev":             round(std_dev, 2),
        "variance_ai_score":   round(variance_ai_score, 4),
        "ttr":                 round(ttr, 4),
        "ttr_ai_score":        round(ttr_ai_score, 4),
        "expressive_count":    expressive_count,
        "punct_density_pct":   round(punct_density * 100, 3),
        "punct_ai_score":      round(punct_ai_score, 4),
        "cv":                  round(cv, 4),
        "consistency_ai_score":round(consistency_ai_score, 4),
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Signal 2 — Stylometric Heuristics  (standalone test)")
    print("=" * 60)

    results = []

    for category, text in SAMPLES:
        print(f"\n[{category}]")
        print(f"  Text : {text[:80]}...")

        # --- Raw metrics ---
        m = raw_metrics(text)
        print("\n  Raw metrics:")
        if "note" in m:
            print(f"    {m['note']}")
        else:
            print(f"    sentences       : {m['num_sentences']}  "
                  f"words: {m['num_words']}")
            print(f"    sent lengths    : {m['sent_lengths']}")
            print(f"    mean / std_dev  : {m['mean_sent_len']} / {m['std_dev']}")
            print(f"    variance score  : {m['variance_ai_score']}  "
                  f"(low std_dev = AI-like)")
            print(f"    TTR             : {m['ttr']}  "
                  f"(unique/total words)")
            print(f"    TTR score       : {m['ttr_ai_score']}  "
                  f"(low TTR = AI-like)")
            print(f"    expressive punct: {m['expressive_count']}  "
                  f"({m['punct_density_pct']}% of chars)")
            print(f"    punct score     : {m['punct_ai_score']}  "
                  f"(sparse punct = AI-like)")
            print(f"    CV              : {m['cv']}  "
                  f"(std_dev / mean)")
            print(f"    consistency scr : {m['consistency_ai_score']}  "
                  f"(low CV = AI-like)")

        # --- Signal scores ---
        stylo_score = analyze_stylometry(text)
        print(f"\n  Signal 2 (stylometric) : {stylo_score:.4f}  "
              f"->  {label_from_score(stylo_score)}")

        results.append((category, text, stylo_score))
        print()

    # --- Cross-signal comparison ---
    print("=" * 60)
    print("Cross-signal comparison (requires GROQ_API_KEY)")
    print("=" * 60)
    print(f"\n{'Sample':<8}  {'Signal 1 (LLM)':>16}  "
          f"{'Signal 2 (Stylo)':>18}  {'Confidence':>12}  "
          f"{'Agree?':>8}  Label")
    print("-" * 80)

    for category, text, stylo_score in results:
        llm_score = classify_with_llm(text)
        confidence = compute_confidence(llm_score, stylo_score)

        # Signals "agree" when both land on the same side of the 0.5 midpoint
        # (both lean human or both lean AI)
        agree = (llm_score < 0.5) == (stylo_score < 0.5)
        agree_str = "YES" if agree else "NO <-"

        print(
            f"{category:<8}  {llm_score:>16.4f}  {stylo_score:>18.4f}  "
            f"{confidence:>12.4f}  {agree_str:>8}  {label_from_score(confidence)}"
        )

    print()
    print("Signals disagree ('NO <-') when the structural and semantic")
    print("analyses pull in opposite directions -- worth investigating.")
