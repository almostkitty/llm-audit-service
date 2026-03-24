from collections import Counter
from math import log2


def text_entropy(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0

    total = len(words)
    counts = Counter(words)

    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * log2(probability)

    return entropy
