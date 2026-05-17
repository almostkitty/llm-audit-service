"""
Агрегированный скор «похожести на LLM» (`llm_probability`) через CatBoost.

Если CatBoost выключен (`ENABLE_CATBOOST=0`), нет файла модели или не удалось
загрузить зависимости — ``llm_probability`` будет ``None``, в ``scoring.mode``
вернётся ``unavailable``.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.services.scoring.catboost_runtime import predict_llm_probability
from app.services.scoring.domain import default_catboost_domain_meta

_DISCLAIMER = (
    "Число llm_probability — не вердикт о происхождении текста: результат нужно "
    "интерпретировать вместе с метриками и источником фрагмента."
)
_UNAVAILABLE_DISCLAIMER = (
    _DISCLAIMER
    + " Сейчас CatBoost недоступен (ENABLE_CATBOOST=0, нет файла модели или ошибка "
    "загрузки); скор не вычислен."
)


def score_with_meta(metrics: Mapping[str, float]) -> tuple[float | None, dict[str, Any]]:
    """
    Возвращает ``(p, meta)``. ``p`` — вероятность класса LLM в ``[0, 1]`` или ``None``,
    если CatBoost недоступен.
    """
    domain = default_catboost_domain_meta()
    cat = predict_llm_probability(metrics)
    if cat is not None:
        p, meta = cat
        return p, {**domain, **meta, "disclaimer": _DISCLAIMER}
    return None, {
        **domain,
        "mode": "unavailable",
        "disclaimer": _UNAVAILABLE_DISCLAIMER,
    }


def compute_score(metrics: Mapping[str, float]) -> float | None:
    """То же число, что в ``score_with_meta``, без поля ``scoring``."""
    p, _ = score_with_meta(metrics)
    return p
