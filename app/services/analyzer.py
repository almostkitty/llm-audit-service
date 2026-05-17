import os

from app.services.preprocessing.cleaner import clean_text
from app.services.metrics.hidden_unicode import find_llm_unicode_signals
from app.services.metrics.lexical_diversity import lexical_diversity
from app.services.metrics.burstiness import burstiness
from app.services.metrics.avg_lenght import average_sentence_length
from app.services.metrics.text_entropy import text_entropy
from app.services.metrics.stop_word import stop_word_ratio
from app.services.metrics.lenght_variation import word_length_variation
from app.services.metrics.punctuation_ratio import punctuation_ratio
from app.services.metrics.repetition_score import repetition_score
from app.services.metrics.perplexity import perplexity
from app.services.scoring import score_with_meta


def analyze_text(text: str) -> dict:
    raw_text = text
    hidden_unicode = find_llm_unicode_signals(raw_text)
    text = clean_text(raw_text)

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
    if os.getenv("ENABLE_PERPLEXITY", "0") == "1":
        metrics["perplexity"] = perplexity(raw_text)

    # Как в manifest: 0/1 по исходной строке (согласовано с пилотной логрегрессией).
    metrics["unicode"] = 1.0 if hidden_unicode.get("has_signals") else 0.0

    # (float | None, dict): без CatBoost score будет None.
    score, _scoring_meta = score_with_meta(metrics)

    return {
        "metrics": metrics,
        "llm_probability": score,
        "hidden_unicode": hidden_unicode,
    }
