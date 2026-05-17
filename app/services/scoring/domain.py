"""Домен обучения и применения модели CatBoost (системная метаинформация)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Единый источник правды для сервиса и JSON рядом с .cbm
CATBOOST_DOMAIN_ID = "vkr_informatics"
CATBOOST_DOMAIN_LABEL_RU = "ВКР по информатике"
CATBOOST_DOMAIN_DESCRIPTION_RU = (
    "Модель CatBoost обучена на выпускных квалификационных работах (ВКР) "
    "по направлению «Информатика и вычислительная техника» и смежным. "
    "Эталон метрик — human-тексты из той же выборки; для других доменов результат "
    "может быть менее надёжным."
)


def default_catboost_domain_meta() -> dict[str, str]:
    return {
        "domain": CATBOOST_DOMAIN_ID,
        "domain_label_ru": CATBOOST_DOMAIN_LABEL_RU,
        "domain_description_ru": CATBOOST_DOMAIN_DESCRIPTION_RU,
    }


def load_catboost_domain_meta(model_path: Path | None = None) -> dict[str, str]:
    """Мета домена: из inference.json / training_meta.json рядом с моделью или значения по умолчанию."""
    meta = default_catboost_domain_meta()
    if model_path is None:
        return meta
    for name in ("inference.json", "training_meta.json", "metrics.json"):
        fp = model_path.parent / name
        if not fp.is_file():
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("domain", "domain_label_ru", "domain_description_ru"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                meta[key] = val.strip()
    return meta


def domain_meta_for_api(extra: dict[str, Any] | None = None) -> dict[str, str]:
    out = default_catboost_domain_meta()
    if extra:
        for key in ("domain", "domain_label_ru", "domain_description_ru"):
            val = extra.get(key)
            if isinstance(val, str) and val.strip():
                out[key] = val.strip()
    return out
