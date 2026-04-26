"""
Колонки таблицы ``dataset_train.csv``: идентификация, целевая переменная, признаки для CatBoost.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

# Не признаки: идентификация строки
ID_COLUMNS: Final[tuple[str, ...]] = ("file_name", "origin")

# Целевая переменная: 0 = human, 1 = LLM
TARGET_COLUMN: Final[str] = "label"


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Имена колонок-признаков (всё, кроме ``file_name``, ``origin``, ``label``)."""
    skip = {*ID_COLUMNS, TARGET_COLUMN}
    return [c for c in df.columns if c not in skip]


def X_y(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Разделяет матрицу признаков и целевой вектор.
    ``y`` — целочисленные метки ``0`` / ``1``.
    """
    feats = feature_columns(df)
    X = df[feats].copy()
    y = df[TARGET_COLUMN].astype(int)
    return X, y
