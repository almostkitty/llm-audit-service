def compute_score(metrics: dict) -> float:
    score = 0.0

    score += (1 - metrics["lexical_diversity"]) * 0.25
    score += metrics["burstiness"] * 0.25
    score += metrics["average_sentence_length"] * 0.25
    score += metrics["text_entropy"] * 0.25

    return min(score, 1.0)