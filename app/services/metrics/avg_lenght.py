import re


def average_sentence_length(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0

    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0

    return len(words) / len(sentences)
