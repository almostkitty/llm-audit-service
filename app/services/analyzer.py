from app.services.preprocessing.cleaner import clean_text
from app.services.metrics.lexical_diversity import lexical_diversity
from app.services.metrics.burstiness import burstiness
from app.services.metrics.avg_lenght import average_sentence_length
from app.services.metrics.text_entropy import text_entropy
from app.services.scoring.aggregator import compute_score

def analyze_text(text: str) -> dict:
    text = clean_text(text)

    metrics = {
        "lexical_diversity": lexical_diversity(text),
        "burstiness": burstiness(text),
        "average_sentence_length": average_sentence_length(text),
        "text_entropy": text_entropy(text),
    }

    score = compute_score(metrics)

    return {
        "metrics": metrics,
        "llm_probability": score
    }