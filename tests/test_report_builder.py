"""Тесты сборки отчёта."""

from datetime import datetime, timezone

from app.services.report_builder import (
    DECISION_THRESHOLD,
    build_audit_report,
    enrich_report_for_display,
)


def test_build_audit_report_structure():
    audit = {
        "metrics": {
            "lexical_diversity": 0.5,
            "burstiness": 4.0,
            "unicode": 0.0,
        },
        "llm_probability": 0.31,
        "scoring": {
            "mode": "catboost",
            "disclaimer": "test disclaimer",
            "domain": "vkr_informatics",
            "domain_label_ru": "ВКР по информатике",
        },
        "hidden_unicode": {"has_signals": False, "total_flagged_characters": 0},
    }
    report = build_audit_report(
        audit,
        filename="thesis.txt",
        text="  Hello world.\nSecond line.  ",
        check_id="abc-123",
        checked_at=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert report["version"] == 1
    assert report["id"] == "abc-123"
    assert report["document"]["filename"] == "thesis.txt"
    assert report["document"]["word_count"] == 4
    assert report["document"]["char_count_display"] == "29/29"


def test_char_count_before_thesis_clean():
    audit = {
        "metrics": {},
        "llm_probability": None,
        "scoring": {},
        "hidden_unicode": {},
    }
    report = build_audit_report(
        audit,
        filename="a.txt",
        text="x" * 41058,
        char_count_before=62822,
    )
    assert report["document"]["char_count_display"] == "62822/41058"
    assert report["document"]["line_count"] == 1
    assert report["summary"]["llm_probability"] is None
    assert report["hidden_unicode"]["has_signals"] is False
    assert report["hidden_unicode"]["summary_display"] == "—"


def test_hidden_unicode_verdict_yes_with_symbols():
    audit = {
        "metrics": {},
        "llm_probability": None,
        "scoring": {},
        "hidden_unicode": {
            "has_signals": True,
            "counts_by_label": {},
            "latex_style_escapes": {"backslash_dollar": 1, "backslash_tilde": 1},
            "total_flagged_characters": 0,
        },
    }
    report = build_audit_report(audit, filename="a.txt", text="x")
    assert report["hidden_unicode"]["summary_display"] == "Да (\\$, \\~)"


def test_decision_llm_side():
    audit = {
        "metrics": {},
        "llm_probability": 0.72,
        "scoring": {"mode": "catboost"},
        "hidden_unicode": {},
    }
    report = build_audit_report(audit, filename="x.txt", text="text")
    assert report["summary"]["decision"]["class_hint"] == "llm"
    assert report["summary"]["decision"]["threshold"] == DECISION_THRESHOLD


def test_metric_rows_have_plain_comparison():
    audit = {
        "metrics": {"lexical_diversity": 0.5, "burstiness": 4.0},
        "llm_probability": 0.2,
        "scoring": {},
        "hidden_unicode": {},
    }
    report = build_audit_report(audit, filename="a.txt", text="word " * 20)
    row = next(m for m in report["metrics"] if m["key"] == "lexical_diversity")
    assert row["baseline_typical"].startswith("≈")
    assert row["comparison"] in ("typical", "higher", "lower", "much_higher", "much_lower")
    assert "эталон" not in row["deviation_note"].lower()
    assert "z" not in row["deviation_note"].lower()


def test_enrich_legacy_report_metrics():
    legacy = {
        "metrics": [
            {
                "key": "burstiness",
                "label_ru": "Burstiness",
                "value": 8.0,
                "value_formatted": "8",
                "baseline": {"mean": 4.14, "std": 0.96},
                "deviation_note": "выше эталона human (|z| ≥ 2)",
                "z_score": 4.0,
            }
        ]
    }
    enriched = enrich_report_for_display(legacy)
    row = enriched["metrics"][0]
    assert row["comparison"] == "much_higher"
    assert row["deviation_note"] == "Заметно выше обычного"
    assert row["strong_deviation"] is True
