"""
Агрегированный скор «похожести на LLM» (`llm_probability`) через CatBoost.

Если CatBoost выключен (`ENABLE_CATBOOST=0`), нет файла модели или не удалось
загрузить зависимости — ``llm_probability`` будет ``None``.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.services.scoring.catboost_runtime import predict_llm_probability


def score_with_meta(metrics: Mapping[str, float]) -> tuple[float | None, dict[str, Any]]:
    """
    Возвращает ``(p, meta)``. ``p`` — вероятность класса LLM в ``[0, 1]`` или ``None``,
    если CatBoost недоступен. ``meta`` зарезервировано и всегда пустое.
    """
    cat = predict_llm_probability(metrics)
    if cat is not None:
        p, _meta = cat
        return p, {}
    return None, {}


def compute_score(metrics: Mapping[str, float]) -> float | None:
    """То же число, что в ``score_with_meta``, без поля ``scoring``."""
    p, _ = score_with_meta(metrics)
    return p
