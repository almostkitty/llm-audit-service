"""
Склеивает ``dataset_human.csv`` и ``dataset_llm.csv`` в один табличный датасет для обучения классификатора.

- Колонка ``label``: **0** = human, **1** = LLM (как в ``corpus_threshold_experiment.py``).
- Колонка ``origin``: строки ``human`` / ``llm`` для читаемости.

Признаки — те же числовые метрики; ``file_name`` и служебные колонки не подаются в модель как признаки
(их нужно исключить при обучении CatBoost / sklearn).

Пример:
  python3 tools/build_classification_dataset.py
  python3 tools/build_classification_dataset.py \\
    --human ml/dataset_human.csv --llm ml/dataset_llm.csv --out ml/catboost/dataset_train.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

META_COLS = ("file_name", "origin", "label")
DEFAULT_HUMAN = PROJECT_ROOT / "ml/dataset_human.csv"
DEFAULT_LLM = PROJECT_ROOT / "ml/dataset_llm.csv"
DEFAULT_OUT = PROJECT_ROOT / "ml/catboost/dataset_train.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    first = path.read_text(encoding="utf-8").splitlines()[0] if path.stat().st_size else ""
    sep = ";" if first.count(";") > first.count(",") else ","
    return pd.read_csv(path, sep=sep)


def main() -> None:
    p = argparse.ArgumentParser(description="Human + LLM CSV → один датасет с label для классификации")
    p.add_argument("--human", type=Path, default=DEFAULT_HUMAN)
    p.add_argument("--llm", type=Path, default=DEFAULT_LLM)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    h = _read_csv(args.human)
    l = _read_csv(args.llm)

    h_cols = set(h.columns)
    l_cols = set(l.columns)
    if h_cols != l_cols:
        only_h = h_cols - l_cols
        only_l = l_cols - h_cols
        raise SystemExit(
            f"Колонки human и llm различаются.\n  только в human: {only_h}\n  только в llm: {only_l}"
        )

    h = h.assign(label=0, origin="human")
    l = l.assign(label=1, origin="llm")

    df = pd.concat([h, l], ignore_index=True)

    # Порядок: идентификация и метка, затем признаки
    feature_cols = [c for c in df.columns if c not in META_COLS]
    ordered = ["file_name", "origin", "label"] + feature_cols
    df = df[ordered]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    n0 = int((df["label"] == 0).sum())
    n1 = int((df["label"] == 1).sum())
    print(f"Записано {len(df)} строк → {args.out}")
    print(f"  human (label=0): {n0}, llm (label=1): {n1}")
    if df["perplexity"].isna().any():
        n_nan = int(df["perplexity"].isna().sum())
        print(
            f"  предупреждение: perplexity пустая у {n_nan} строк — "
            "для CatBoost это ок (NaN как пропуск); при обучении можно выкинуть колонку.",
            file=sys.stderr,
        )
    print(
        "\nПризнаки для модели (без file_name/origin/label): "
        + ", ".join(feature_cols),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
