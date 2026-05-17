"""Сборка структурированного отчёта по результату /audit."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from app.services.scoring.domain import default_catboost_domain_meta

REPORT_VERSION = 1
DECISION_THRESHOLD = 0.5
STRONG_DEVIATION_Z = 2.0
_REPORT_SKIP_METRICS = frozenset({"perplexity"})

_METRIC_ORDER = (
    "lexical_diversity",
    "burstiness",
    "average_sentence_length",
    "text_entropy",
    "stop_word_ratio",
    "word_length_variation",
    "punctuation_ratio",
    "repetition_score",
    "unicode",
)

_MODE_LABELS_RU = {
    "catboost": "Модель CatBoost",
    "unavailable": "CatBoost недоступен",
}

_BASELINES_PATH = (
    Path(__file__).resolve().parents[1] / "static" / "data" / "metric_baselines_human.json"
)


@lru_cache(maxsize=1)
def load_metric_baselines() -> dict[str, Any]:
    if not _BASELINES_PATH.is_file():
        return {"metrics": {}}
    return json.loads(_BASELINES_PATH.read_text(encoding="utf-8"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_char_count_display(before: int, after: int) -> str:
    """До обработки / текст проверки, например 62822/41058."""
    return f"{max(0, before)}/{max(0, after)}"


def _text_stats(text: str, *, char_count_before: int | None = None) -> dict[str, int | str]:
    stripped = text.strip()
    words = re.findall(r"\S+", stripped)
    lines = stripped.splitlines() if stripped else []
    char_count_after = len(text)
    char_count_before_val = char_count_before if char_count_before is not None else char_count_after
    char_count_before_val = max(char_count_before_val, char_count_after)
    return {
        "char_count": char_count_before_val,
        "char_count_after": char_count_after,
        "char_count_stripped": char_count_after,
        "char_count_display": _format_char_count_display(
            char_count_before_val,
            char_count_after,
        ),
        "word_count": len(words),
        "line_count": len(lines),
    }


def _format_checked_at(dt: datetime | None) -> str:
    if dt is None:
        return _utc_now_iso()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _decision_summary(llm_probability: float | None) -> dict[str, Any]:
    if llm_probability is None or (
        isinstance(llm_probability, float) and math.isnan(llm_probability)
    ):
        return {
            "threshold": DECISION_THRESHOLD,
            "label": "Оценка P(LLM) не вычислена",
            "class_hint": None,
        }
    p = float(llm_probability)
    if p >= DECISION_THRESHOLD:
        return {
            "threshold": DECISION_THRESHOLD,
            "label": (
                f"По порогу {DECISION_THRESHOLD}: признаки, характерные для LLM-текстов "
                f"(P(LLM) = {p:.4f})"
            ),
            "class_hint": "llm",
        }
    return {
        "threshold": DECISION_THRESHOLD,
        "label": (
            f"По порогу {DECISION_THRESHOLD}: ближе к эталону человеческих текстов "
            f"(P(LLM) = {p:.4f})"
        ),
        "class_hint": "human",
    }


def _format_typical_value(mean: float | None) -> str | None:
    if mean is None or (isinstance(mean, float) and math.isnan(mean)):
        return None
    return f"≈ {float(mean):.4g}"


def _metric_deviation(
    value: float,
    *,
    mean: float | None,
    std: float | None,
) -> dict[str, Any]:
    if mean is None or std is None or std <= 0 or math.isnan(std):
        return {
            "z_score": None,
            "note": "Нет данных для сравнения",
            "comparison": "unknown",
        }
    z = (value - mean) / std
    abs_z = abs(z)
    if abs_z < 0.5:
        note = "Близко к обычному"
        comparison = "typical"
    elif z > 0:
        if abs_z >= STRONG_DEVIATION_Z:
            note = "Заметно выше обычного"
            comparison = "much_higher"
        else:
            note = "Немного выше обычного"
            comparison = "higher"
    elif abs_z >= STRONG_DEVIATION_Z:
        note = "Заметно ниже обычного"
        comparison = "much_lower"
    else:
        note = "Немного ниже обычного"
        comparison = "lower"
    return {"z_score": round(z, 3), "note": note, "comparison": comparison}


def _metric_strong_deviation(comparison: str | None) -> bool:
    return comparison in ("much_higher", "much_lower")


def _build_metrics_rows(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    baselines = load_metric_baselines().get("metrics") or {}
    rows: list[dict[str, Any]] = []
    keys = list(_METRIC_ORDER) + [k for k in metrics if k not in _METRIC_ORDER]

    for key in keys:
        if key in _REPORT_SKIP_METRICS or key not in metrics:
            continue
        raw = metrics[key]
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isnan(value) or math.isinf(value):
            continue

        bl = baselines.get(key) or {}
        mean = bl.get("mean")
        std = bl.get("std")
        if mean is not None:
            mean = float(mean)
        if std is not None:
            std = float(std)

        dev = _metric_deviation(value, mean=mean, std=std)
        rows.append(
            {
                "key": key,
                "label_ru": bl.get("label_ru") or key,
                "value": value,
                "value_formatted": f"{value:.6g}",
                "baseline_typical": _format_typical_value(mean),
                "baseline": {
                    "n": bl.get("n"),
                    "mean": mean,
                    "std": std,
                    "distribution": bl.get("distribution"),
                },
                "z_score": dev["z_score"],
                "deviation_note": dev["note"],
                "comparison": dev["comparison"],
                "strong_deviation": _metric_strong_deviation(dev["comparison"]),
            }
        )
    return rows


_UNICODE_SYMBOL_SHORT: dict[str, str] = {
    "NBSP": "неразрывный пробел (NBSP)",
    "NARROW_NBSP": "узкий NBSP",
    "ZERO_WIDTH_SPACE": "невидимый пробел (ZWSP)",
    "ZERO_WIDTH_NON_JOINER": "ZWNJ",
    "ZERO_WIDTH_JOINER": "ZWJ",
    "WORD_JOINER": "символ-склейка",
    "ZWNBSP_OR_BOM": "BOM",
    "LRM": "LRM",
    "RLM": "RLM",
    "LRE": "LRE",
    "RLE": "RLE",
    "PDF": "PDF",
    "LRO": "LRO",
    "RLO": "RLO",
}


def _hidden_unicode_symbol_list(hidden: Mapping[str, Any]) -> list[str]:
    symbols: list[str] = []
    esc = hidden.get("latex_style_escapes") or {}
    if int(esc.get("backslash_dollar") or 0) > 0:
        symbols.append(r"\$")
    if int(esc.get("backslash_tilde") or 0) > 0:
        symbols.append(r"\~")
    by_label = hidden.get("counts_by_label") or {}
    for name in sorted(by_label.keys()):
        symbols.append(_UNICODE_SYMBOL_SHORT.get(name, name))
    return symbols


def _hidden_unicode_summary(hidden: Mapping[str, Any] | None) -> dict[str, Any]:
    if not hidden:
        return {
            "has_signals": False,
            "verdict": "—",
            "summary_display": "—",
            "symbols": [],
            "summary_lines": ["—"],
            "details": hidden,
        }

    if not hidden.get("has_signals"):
        return {
            "has_signals": False,
            "verdict": "Нет",
            "summary_display": "Нет",
            "symbols": [],
            "summary_lines": ["Нет"],
            "details": hidden,
        }

    symbols = _hidden_unicode_symbol_list(hidden)
    summary_display = f"Да ({', '.join(symbols)})" if symbols else "Да"
    return {
        "has_signals": True,
        "verdict": "Да",
        "summary_display": summary_display,
        "symbols": symbols,
        "summary_lines": [summary_display],
        "details": hidden,
    }


def build_audit_report(
    audit_result: Mapping[str, Any],
    *,
    filename: str | None,
    text: str,
    check_id: str | None = None,
    checked_at: datetime | None = None,
    char_count_before: int | None = None,
) -> dict[str, Any]:
    """
    Полный отчёт: документ, итог, метрики с эталоном, Unicode, служебные поля.
    """
    metrics = dict(audit_result.get("metrics") or {})
    scoring = dict(audit_result.get("scoring") or {})
    llm_p = audit_result.get("llm_probability")
    if isinstance(llm_p, (int, float)) and not math.isnan(float(llm_p)):
        llm_probability: float | None = float(llm_p)
    else:
        llm_probability = None

    baselines_payload = load_metric_baselines()
    mode = scoring.get("mode")
    checked_iso = _format_checked_at(checked_at)
    report_id = check_id or "draft"

    return {
        "version": REPORT_VERSION,
        "id": report_id,
        "generated_at": _utc_now_iso(),
        "document": {
            "filename": (filename or "").strip() or "input.txt",
            **_text_stats(text, char_count_before=char_count_before),
        },
        "check": {
            "id": check_id,
            "checked_at": checked_iso,
        },
        "summary": {
            "llm_probability": llm_probability,
            "llm_probability_formatted": (
                f"{llm_probability:.4f}" if llm_probability is not None else None
            ),
            "decision": _decision_summary(llm_probability),
            "scoring_mode": mode,
            "scoring_mode_label": _MODE_LABELS_RU.get(str(mode), str(mode) if mode else "—"),
            "disclaimer": scoring.get("disclaimer") or "",
            "model_path": scoring.get("model_path"),
            "domain": scoring.get("domain"),
            "domain_label_ru": scoring.get("domain_label_ru"),
            "domain_description_ru": scoring.get("domain_description_ru"),
        },
        "metrics": _build_metrics_rows(metrics),
        "hidden_unicode": _hidden_unicode_summary(audit_result.get("hidden_unicode")),
        "service": {
            "name": "LLM Audit",
            "perplexity_enabled": os.getenv("ENABLE_PERPLEXITY", "0") == "1",
            "catboost_enabled": os.getenv("ENABLE_CATBOOST", "0") == "1",
            "catboost_domain": {
                "id": scoring.get("domain"),
                "label_ru": scoring.get("domain_label_ru"),
                "description_ru": scoring.get("domain_description_ru"),
            },
            "baselines": {
                "version": baselines_payload.get("version"),
                "generated_at": baselines_payload.get("generated_at"),
                "source": baselines_payload.get("source"),
                "description": baselines_payload.get("description"),
            },
        },
    }


def enrich_report_for_display(report: dict[str, Any]) -> dict[str, Any]:
    """Дополняет строки метрик полями для UI (в т.ч. для старых report_json)."""
    document = report.get("document")
    if isinstance(document, dict):
        before = document.get("char_count")
        after = document.get("char_count_after", document.get("char_count_stripped"))
        if before is not None and after is not None:
            try:
                document["char_count_display"] = _format_char_count_display(
                    int(before),
                    int(after),
                )
            except (TypeError, ValueError):
                pass

    metrics = report.get("metrics")
    if isinstance(metrics, list):
        for row in metrics:
            if not isinstance(row, dict):
                continue
            value = row.get("value")
            if value is None:
                continue
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                continue
            baseline = row.get("baseline") if isinstance(row.get("baseline"), dict) else {}
            mean = baseline.get("mean")
            std = baseline.get("std")
            if mean is not None:
                mean = float(mean)
            if std is not None:
                std = float(std)
            dev = _metric_deviation(value_f, mean=mean, std=std)
            row["baseline_typical"] = _format_typical_value(mean)
            row["comparison"] = dev["comparison"]
            row["deviation_note"] = dev["note"]
            row["z_score"] = dev["z_score"]
            row["strong_deviation"] = _metric_strong_deviation(dev["comparison"])

    hidden = report.get("hidden_unicode")
    if isinstance(hidden, dict):
        raw = hidden.get("details")
        if isinstance(raw, dict) and (
            "has_signals" in raw or "latex_style_escapes" in raw
        ):
            report["hidden_unicode"] = _hidden_unicode_summary(raw)

    summary = report.get("summary")
    if isinstance(summary, dict) and not summary.get("domain_label_ru"):
        domain = default_catboost_domain_meta()
        summary.setdefault("domain", domain["domain"])
        summary.setdefault("domain_label_ru", domain["domain_label_ru"])
        summary.setdefault("domain_description_ru", domain["domain_description_ru"])
    service = report.get("service")
    if isinstance(service, dict):
        cb = service.get("catboost_domain")
        if not isinstance(cb, dict) or not cb.get("label_ru"):
            domain = default_catboost_domain_meta()
            service["catboost_domain"] = {
                "id": domain["domain"],
                "label_ru": domain["domain_label_ru"],
                "description_ru": domain["domain_description_ru"],
            }

    return report


def report_from_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return enrich_report_for_display(data)
