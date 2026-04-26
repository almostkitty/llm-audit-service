"""
Обучение CatBoost: стратифицированное разбиение, сохранение модели и метрик.

Запуск из корня репозитория:
  python3 -m ml.catboost.train
  python3 -m ml.catboost.train --test-size 0.25 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from .schema import TARGET_COLUMN, X_y

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dataset(path: Path) -> pd.DataFrame:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    sep = ";" if first.count(";") > first.count(",") else ","
    return pd.read_csv(path, sep=sep)


def main() -> None:
    p = argparse.ArgumentParser(description="CatBoost: train/test по dataset_train.csv")
    p.add_argument(
        "--data",
        type=Path,
        default=PROJECT_ROOT / "ml/catboost/dataset_train.csv",
        help="CSV с колонками file_name, origin, label, признаки",
    )
    p.add_argument("--test-size", type=float, default=0.25, help="Доля теста (стратификация по label)")
    p.add_argument("--seed", type=int, default=42, help="random_state для split")
    p.add_argument(
        "--out-model",
        type=Path,
        default=PROJECT_ROOT / "ml/catboost/model.cbm",
        help="Куда сохранить обученную модель",
    )
    p.add_argument(
        "--out-metrics",
        type=Path,
        default=PROJECT_ROOT / "ml/catboost/metrics.json",
        help="JSON с метриками на тесте",
    )
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument("--early-stopping-rounds", type=int, default=30)
    args = p.parse_args()

    try:
        from catboost import CatBoostClassifier, Pool
    except ImportError as exc:
        raise SystemExit(
            "Установи catboost: pip install catboost\n" + str(exc)
        ) from exc

    if not args.data.is_file():
        raise SystemExit(f"Нет файла: {args.data}")

    df = load_dataset(args.data)
    if TARGET_COLUMN not in df.columns:
        raise SystemExit(f"В данных нет колонки {TARGET_COLUMN!r}")

    X, y = X_y(df)
    # CatBoost: NaN в признаках допустимы; убедимся, что только числа
    for c in X.columns:
        if not pd.api.types.is_numeric_dtype(X[c]):
            raise SystemExit(f"Нечисловая колонка-признак: {c!r}")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y,
    )

    train_pool = Pool(X_train, y_train)
    eval_pool = Pool(X_test, y_test)

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        iterations=args.iterations,
        early_stopping_rounds=args.early_stopping_rounds,
        random_seed=args.seed,
        verbose=False,
        auto_class_weights="Balanced",
    )
    model.fit(train_pool, eval_set=eval_pool, use_best_model=True)

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test).astype(int)

    report = classification_report(
        y_test, y_pred, labels=[0, 1], target_names=["human", "llm"], output_dict=True
    )
    auc = float(roc_auc_score(y_test, y_proba))

    metrics: dict[str, Any] = {
        "n_total": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "feature_names": list(X.columns),
        "roc_auc_test": auc,
        "classification_report_test": report,
        "best_iteration": int(model.get_best_iteration() or 0),
    }

    args.out_model.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(args.out_model))

    inference_sidecar = args.out_model.with_name("inference.json")
    inference_sidecar.write_text(
        json.dumps({"feature_names": list(X.columns)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    args.out_metrics.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Модель → {args.out_model}")
    print(f"Признаки для API → {inference_sidecar}")
    print(f"Метрики → {args.out_metrics}")
    print(f"ROC-AUC (test): {auc:.4f}")
    print(classification_report(y_test, y_pred, labels=[0, 1], target_names=["human", "llm"]))


if __name__ == "__main__":
    main()
