#!/usr/bin/env python3
"""
Считает по ml/dataset_human.csv описательную статистику и параметры нормального приближения
(μ = среднее, σ = выборочное стандартное отклонение, n-1 в знаменателе при n > 1).

Результат: app/static/data/metric_baselines_human.json — для визуализации на /demo
(положение значения текста относительно распределения метрик по корпусу human).

Запуск из корня репозитория:
    python3 tools/build_human_metric_baselines.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "ml" / "dataset_human.csv"
DEFAULT_OUT = PROJECT_ROOT / "app" / "static" / "data" / "metric_baselines_human.json"

# Совпадает с ключами в ответе /audit (metrics)
METRIC_ORDER = [
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
]

LABELS_RU: dict[str, str] = {
    "unicode": "Unicode 0/1",
    "lexical_diversity": "Лексическое разнообразие",
    "burstiness": "Burstiness",
    "average_sentence_length": "Средняя длина предложения",
    "text_entropy": "Энтропия текста",
    "stop_word_ratio": "Доля стоп-слов",
    "word_length_variation": "Вариация длины слов",
    "punctuation_ratio": "Доля пунктуации",
    "repetition_score": "Повторяемость",
    "perplexity": "Перплексия",
}


def _series_stats(s: pd.Series) -> dict:
    s = pd.to_numeric(s, errors="coerce").dropna()
    n = int(s.shape[0])
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    arr = s.to_numpy(dtype=np.float64)
    mean = float(np.mean(arr))
    if n == 1:
        std = 0.0
    else:
        std = float(np.std(arr, ddof=1))
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def build(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    missing = [c for c in METRIC_ORDER if c not in df.columns]
    if missing:
        raise SystemExit(f"В CSV нет колонок: {missing}")

    metrics_out: dict[str, dict] = {}
    for key in METRIC_ORDER:
        st = _series_stats(df[key])
        if st["n"] == 0:
            dist = "empty"
        elif key == "unicode":
            dist = "bernoulli"
        else:
            dist = "normal"
        entry = {
            "label_ru": LABELS_RU.get(key, key),
            "distribution": dist,
            **st,
        }
        metrics_out[key] = entry

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(csv_path.relative_to(PROJECT_ROOT)),
            "rows_in_file": int(len(df)),
        },
        "description": (
            "Параметры для визуализации: для непрерывных метрик — μ и σ по выборке human; "
            "unicode — бинарный признак (μ = доля единиц). Пустая перплексия в CSV исключается из n."
        ),
        "metrics": metrics_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"Нет файла: {args.csv}")

    payload = build(args.csv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Written {args.out} ({payload['source']['path']}, metrics: {len(METRIC_ORDER)})")


if __name__ == "__main__":
    main()
