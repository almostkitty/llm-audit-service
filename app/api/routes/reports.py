"""Заготовка API для отчётов анализа."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/reports", tags=["reports"])
_last_report: dict[str, object] | None = None


def save_last_report(audit_result: dict[str, object]) -> None:
    global _last_report
    _last_report = {
        "id": "last",
        "title": "Последний отчёт проверки",
        "status": "ready",
        "summary": "Последний результат, полученный через /audit.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audit": audit_result,
    }


@router.get("")
def list_reports() -> dict[str, object]:
    items: list[dict[str, str]] = [
        {"id": "demo", "title": "Демо-отчёт проверки"},
    ]
    if _last_report is not None:
        items.append({"id": "last", "title": "Последний отчёт проверки"})
    return {
        "items": items,
        "total": len(items),
    }


@router.get("/{report_id}")
def get_report(report_id: str) -> dict[str, object]:
    if report_id == "last":
        if _last_report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Отчёт 'last' пока недоступен: сначала вызовите /audit",
            )
        return _last_report
    if report_id != "demo":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Отчёт '{report_id}' не найден",
        )
    return {
        "id": "demo",
        "title": "Демо-отчёт проверки",
        "status": "ready",
        "summary": "Тестовый отчёт для отладки API и интерфейса.",
        "metrics": {
            "llm_probability": 0.42,
            "mode": "demo",
        },
    }
