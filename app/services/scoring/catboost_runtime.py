"""
Инференс CatBoost для ``llm_probability`` в веб-сервисе.

Включение: ``ENABLE_CATBOOST=1`` и файл модели (см. ``CATBOOST_MODEL_PATH``).
Порядок признаков — из ``inference.json`` рядом с ``.cbm`` (пишет ``ml/catboost/train.py``),
иначе из ``metrics.json``.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_model_path() -> Path:
    return _project_root() / "ml/catboost/model.cbm"


def _resolve_model_path() -> Path | None:
    raw = os.getenv("CATBOOST_MODEL_PATH", "").strip()
    p = Path(raw) if raw else _default_model_path()
    if not p.is_file():
        return None
    return p.resolve()


def _load_feature_names(model_path: Path) -> list[str]:
    d = model_path.parent
    for name in ("inference.json", "metrics.json"):
        fp = d / name
        if fp.is_file():
            data = json.loads(fp.read_text(encoding="utf-8"))
            fn = data.get("feature_names")
            if isinstance(fn, list) and fn:
                return [str(x) for x in fn]
    raise FileNotFoundError(
        f"Нет inference.json / metrics.json с feature_names рядом с {model_path}"
    )


@lru_cache(maxsize=1)
def _load_model_and_features(model_path_str: str) -> tuple[Any, list[str]]:
    from catboost import CatBoostClassifier

    model_path = Path(model_path_str)
    model = CatBoostClassifier()
    model.load_model(str(model_path))
    features = _load_feature_names(model_path)
    return model, features


def _metric_value(metrics: Mapping[str, Any], key: str) -> float:
    if key not in metrics:
        return float("nan")
    v = metrics[key]
    if v is None:
        return float("nan")
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(x) or math.isinf(x):
        return float("nan")
    return x


def predict_llm_probability(metrics: Mapping[str, Any]) -> tuple[float, dict[str, Any]] | None:
    """
    Возвращает ``(p_llm, meta)`` или ``None``, если CatBoost выключен / нет модели / ошибка импорта.
    """
    if os.getenv("ENABLE_CATBOOST", "0") != "1":
        return None

    model_path = _resolve_model_path()
    if model_path is None:
        return None

    try:
        model, feature_names = _load_model_and_features(str(model_path))
    except ImportError:
        return None
    except OSError:
        return None

    row = {k: _metric_value(metrics, k) for k in feature_names}
    X = pd.DataFrame([row], columns=feature_names)
    proba = model.predict_proba(X)[0]
    # класс 1 = LLM
    p = float(proba[1]) if len(proba) > 1 else float(proba[0])
    p = max(0.0, min(1.0, p))

    meta: dict[str, Any] = {
        "mode": "catboost",
        "model_path": str(model_path)
    }
    return p, meta


def clear_model_cache() -> None:
    """Для тестов после подмены файла модели."""
    _load_model_and_features.cache_clear()
