from app.services.preprocessing.cleaner import clean_text
from app.services.metrics.lexical_diversity import lexical_diversity
from app.services.metrics.burstiness import burstiness
from app.services.metrics.avg_lenght import average_sentence_length
from app.services.metrics.text_entropy import text_entropy
from app.services.metrics.stop_word import stop_word_ratio
from app.services.metrics.lenght_variation import word_length_variation
from app.services.metrics.punctuation_ratio import punctuation_ratio
from app.services.metrics.repetition_score import repetition_score
from app.services.scoring.aggregator import compute_score


def analyze_text(text: str) -> dict:
    text = clean_text(text)

    metrics = {
        "lexical_diversity": lexical_diversity(text),
        "burstiness": burstiness(text),
        "average_sentence_length": average_sentence_length(text),
        "text_entropy": text_entropy(text),
        "stop_word_ratio": stop_word_ratio(text),
        "word_length_variation": word_length_variation(text),
        "punctuation_ratio": punctuation_ratio(text),
        "repetition_score": repetition_score(text),
    }

    score = compute_score(metrics)

    return {
        "metrics": metrics,
        "llm_probability": score,
    }
