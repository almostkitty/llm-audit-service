from app.services.preprocessing.cleaner import clean_text
from app.services.metrics.lexical_diversity import lexical_diversity
from app.services.metrics.burstiness import burstiness
from app.services.scoring.aggregator import compute_score

def analyze_text(text: str) -> dict:
    text = clean_text(text)

    metrics = {
        "lexical_diversity": lexical_diversity(text),
        "burstiness": burstiness(text),
    }

    score = compute_score(metrics)

    return {
        "metrics": metrics,
        "llm_probability": score
    }