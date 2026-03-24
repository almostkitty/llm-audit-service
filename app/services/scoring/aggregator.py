def compute_score(metrics: dict) -> float:
    score = 0.0

    score += (1 - metrics["lexical_diversity"]) * 0.5
    score += metrics["burstiness"] * 0.5

    return min(score, 1.0)