"""
Агрегированный скор «похожести на LLM» (`llm_probability`).

Основной режим — та же логистическая регрессия, что в офлайн-экспериментах:
стандартизация признаков (как в `StandardScaler` на пилотном корпусе) и сигмоида от логита.
Параметры синхронизированы с файлом `threshold_experiment.json` (пилот *n* = 24).

Если нет `perplexity` (не включён `ENABLE_PERPLEXITY=1`), используется прежняя эвристика
по четырём метрикам — чтобы `/audit` оставался рабочим без тяжёлых зависимостей.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.services.scoring.catboost_runtime import predict_llm_probability

# Порядок и значения — из пилотного обучения (см. threshold_experiment.json → logistic_regression).
_LOGREG_FEATURES = (
    "unicode",
    "lexical_diversity",
    "burstiness",
    "average_sentence_length",
    "text_entropy",
    "stop_word_ratio",
    "word_length_variation",
    "punctuation_ratio",
    "repetition_score",
    "perplexity",
)
_LOGREG_INTERCEPT = -0.01773253497909521
_LOGREG_MEAN = (
    0.25,
    0.5332127707121667,
    3.9945149983178196,
    15.054537942090533,
    9.685355187704763,
    0.19014122427726013,
    3.6954416620943995,
    0.025174946643422232,
    0.06928563944707512,
    21.21681348482768,
)
_LOGREG_SCALE = (
    0.4330127018922193,
    0.06972949447763303,
    0.24380955993274653,
    2.2585141819403245,
    0.27125431393044636,
    0.012425945852260823,
    0.17418107701777208,
    0.0030037506226558925,
    0.030295073755256703,
    3.943676110451302,
)
_LOGREG_COEF = (
    -0.6874026151873704,
    0.8349726875869576,
    0.0005974858533529337,
    0.14543717624687488,
    -0.12010288938969628,
    -0.24108649921073558,
    1.1793250356972607,
    0.07243671774680426,
    -1.0655446628748904,
    -0.1470221916001374,
)


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _logreg_logit_and_rows(metrics: Mapping[str, float]) -> tuple[float, list[dict[str, Any]]]:
    logit = _LOGREG_INTERCEPT
    rows: list[dict[str, Any]] = []
    for key, mean, scale, w in zip(_LOGREG_FEATURES, _LOGREG_MEAN, _LOGREG_SCALE, _LOGREG_COEF):
        x = float(metrics[key])
        if scale == 0.0:
            z = 0.0
        else:
            z = (x - mean) / scale
        to_logit = w * z
        logit += to_logit
        rows.append(
            {
                "feature": key,
                "z_score": z,
                "coef": w,
                "to_logit": to_logit,
            }
        )
    rows.sort(key=lambda r: abs(float(r["to_logit"])), reverse=True)
    return logit, rows


def _compute_logreg_llm_probability(metrics: Mapping[str, float]) -> float:
    logit, _ = _logreg_logit_and_rows(metrics)
    return max(0.0, min(1.0, _sigmoid(logit)))


def _has_logreg_inputs(metrics: Mapping[str, object]) -> bool:
    return all(k in metrics for k in _LOGREG_FEATURES)


def _compute_legacy_heuristic(metrics: Mapping[str, float]) -> float:
    score = 0.0
    score += (1.0 - metrics["lexical_diversity"]) * 0.25
    score += metrics["burstiness"] * 0.25
    score += metrics["average_sentence_length"] * 0.25
    score += metrics["text_entropy"] * 0.25
    return min(score, 1.0)


def score_with_meta(metrics: Mapping[str, float]) -> tuple[float, dict[str, Any]]:
    """
    То же, что compute_score, плюс поля для прозрачности (logit, вклад признаков, дисклеймер).

    При ``ENABLE_CATBOOST=1`` и наличии файла модели — приоритет **CatBoost** (табличные метрики
    как при обучении); иначе пилотная логрегрессия или запасная эвристика.
    """
    cat = predict_llm_probability(metrics)
    if cat is not None:
        return cat

    if _has_logreg_inputs(metrics):
        logit, rows = _logreg_logit_and_rows(metrics)
        p = max(0.0, min(1.0, _sigmoid(logit)))
        meta: dict[str, Any] = {
            "mode": "logreg_pilot",
            "logit": logit,
            "feature_contributions": rows
        }
        return p, meta
    p = _compute_legacy_heuristic(metrics)
    return p, {
        "mode": "legacy_heuristic",
        "logit": None,
        "feature_contributions": None
    }


def compute_score(metrics: Mapping[str, float]) -> float:
    """Согласовано с ``score_with_meta`` (включая CatBoost при ``ENABLE_CATBOOST=1``)."""
    p, _ = score_with_meta(metrics)
    return p
