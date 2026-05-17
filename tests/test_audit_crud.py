"""CRUD проверок: Create POST /audit, Read history и reports (Update/Delete только каскадом при удалении аккаунта)."""

from __future__ import annotations

from sqlmodel import select

from app.api.routes import reports as reports_routes
from app.db.models import AuditCheck, User
from app.services.audit_history import (
    audit_check_to_dict,
    delete_checks_for_user,
    get_check_report_for_user,
    record_audit_check,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _minimal_audit() -> dict:
    return {
        "metrics": {"lexical_diversity": 0.5, "burstiness": 4.0},
        "llm_probability": 0.33,
        "scoring": {"mode": "unavailable"},
        "hidden_unicode": {"has_signals": False, "total_flagged_characters": 0},
    }


def test_audit_create_with_chars_before(client, register_user):
    token = register_user("chars@example.com")
    text = "Короткий текст после очистки."
    res = client.post(
        "/audit",
        headers=_auth(token),
        files={"file": ("work.txt", text.encode("utf-8"), "text/plain")},
        data={"chars_before": "5000"},
    )
    assert res.status_code == 200
    check_id = res.json()["check_id"]

    report = client.get(f"/api/reports/{check_id}", headers=_auth(token))
    assert report.status_code == 200
    assert report.json()["document"]["char_count_display"].startswith("5000/")


def test_audit_history_empty(client, register_user):
    token = register_user("nohist@example.com")
    res = client.get("/api/audit-history", headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}


def test_reports_list_api(client, register_user):
    token = register_user("list@example.com")
    empty = client.get("/api/reports", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    client.post(
        "/audit",
        headers=_auth(token),
        files={"file": ("a.txt", "Текст для списка отчётов.".encode(), "text/plain")},
    )
    listed = client.get("/api/reports", headers=_auth(token))
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["has_report"] is True
    assert body["items"][0]["title"] == "a.txt"


def test_report_last_from_memory_cache(client, register_user):
    token = register_user("cache@example.com")
    audit = client.post(
        "/audit",
        headers=_auth(token),
        files={"file": ("c.txt", "Кэш последнего отчёта.".encode(), "text/plain")},
    )
    check_id = audit.json()["check_id"]

    last = client.get("/api/reports/last", headers=_auth(token))
    assert last.status_code == 200
    assert last.json()["id"] == check_id


def test_report_last_not_found(client, register_user):
    token = register_user("nolast@example.com")
    reports_routes._last_reports.clear()
    res = client.get("/api/reports/last", headers=_auth(token))
    assert res.status_code == 404


def test_report_missing_check(client, register_user):
    token = register_user("nomiss@example.com")
    res = client.get(
        "/api/reports/00000000-0000-0000-0000-000000000001",
        headers=_auth(token),
    )
    assert res.status_code == 404


def test_report_without_report_json(client, register_user, session):
    token = register_user("legacy@example.com")
    user = session.exec(select(User).where(User.email == "legacy@example.com")).first()
    assert user and user.id is not None

    row = AuditCheck(
        id="00000000-0000-0000-0000-000000000099",
        user_id=user.id,
        filename="old.txt",
        report_json=None,
        llm_probability=0.5,
    )
    session.add(row)
    session.commit()

    res = client.get(
        f"/api/reports/{row.id}",
        headers=_auth(token),
    )
    assert res.status_code == 404
    assert "не сохранён" in res.json()["detail"].lower()


def test_delete_checks_for_user_service(session, register_user, client):
    token = register_user("cascade@example.com")
    user = session.exec(select(User).where(User.email == "cascade@example.com")).first()
    assert user and user.id is not None

    row, _ = record_audit_check(
        session,
        user_id=user.id,
        filename="d.txt",
        text="удаление",
        audit_result=_minimal_audit(),
    )
    assert row.id is not None

    delete_checks_for_user(session, user.id)
    session.commit()

    assert session.get(AuditCheck, row.id) is None
    hist = client.get("/api/audit-history", headers=_auth(token))
    assert hist.json()["total"] == 0


def test_audit_check_to_dict_and_get_report_service(session, register_user):
    token = register_user("svc@example.com")
    user = session.exec(select(User).where(User.email == "svc@example.com")).first()
    assert user

    row, report = record_audit_check(
        session,
        user_id=user.id,
        filename="s.txt",
        text="сервис",
        audit_result=_minimal_audit(),
    )
    d = audit_check_to_dict(row)
    assert d["id"] == row.id
    assert d["has_report"] is True

    loaded = get_check_report_for_user(session, row.id, user)
    assert loaded is not None
    assert loaded["id"] == report["id"]

    missing = get_check_report_for_user(session, "no-such-id", user)
    assert missing is None


def test_thesis_clean_rejects_empty_input(client):
    res = client.post("/thesis-clean", json={"text": "   \n\t  "})
    assert res.status_code == 422
    assert "Пустой текст" in res.json()["detail"]


def test_thesis_clean_rejects_when_nothing_left(client):
    res = client.post("/thesis-clean", json={"text": "Список литературы\n\n1. Книга."})
    assert res.status_code == 422
    assert "После очистки" in res.json()["detail"]


def test_safe_filename_edge_cases(session, register_user):
    register_user("fname@example.com")
    user = session.exec(select(User).where(User.email == "fname@example.com")).first()
    assert user and user.id is not None

    row_none, _ = record_audit_check(
        session,
        user_id=user.id,
        filename=None,
        text="x",
        audit_result=_minimal_audit(),
    )
    assert row_none.filename == "input.txt"

    long_name = "a" * 300 + ".txt"
    row_long, _ = record_audit_check(
        session,
        user_id=user.id,
        filename=long_name,
        text="y",
        audit_result=_minimal_audit(),
    )
    assert row_long.filename.endswith("...")
    assert len(row_long.filename) == 255

    row_slash, _ = record_audit_check(
        session,
        user_id=user.id,
        filename="///",
        text="z",
        audit_result=_minimal_audit(),
    )
    assert row_slash.filename == "input.txt"
