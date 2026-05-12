"""Скоринг: CatBoost (см. ``catboost_runtime``)."""

from app.services.scoring.aggregator import compute_score, score_with_meta

__all__ = ["compute_score", "score_with_meta"]
