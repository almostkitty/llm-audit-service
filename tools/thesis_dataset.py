"""
Батч ВКР из публикаций НИУ ВШЭ: файлы ``<id>_<название>.{pdf,docx,...}`` в каталоге → SQLite и txt.

Только для твоей папки с работами ВШЭ. Разбор ``id`` и ``title`` из имени файла — см. ``parse_filename_stem``.

Обработка текста (рефераты, главы, артефакты) — в ``app.services.preprocessing.vkr_text``; после этого
для датасета ВШЭ дополнительно срезается типовой титульный блок (шаблон НИУ ВШЭ / ФКН) —
см. ``strip_leading_hse_title_block``.

Постобработка уже сохранённых ``works.text`` и ``*.txt`` без повторного PDF:
``strip_hse_title_from_stored`` (``--strip-hse-title``, ``--strip-bibliography``).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Callable

from app.services.preprocessing.vkr_text import (
    _BODY_START,
    clean_thesis_text,
    load_document_text,
    strip_trailing_bibliography_section,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_HSE_TITLE_HINTS_RU: tuple[re.Pattern[str], ...] = (
    re.compile(r"Высшая школа экономики", re.I),
    re.compile(r"Национальный исследовательский", re.I),
    re.compile(r"Федеральное\s+государственное", re.I),
    re.compile(r"Факультет\s+компьютерных\s+наук", re.I),
    re.compile(r"ВЫПУСКНАЯ\s+КВАЛИФИКАЦИОННАЯ\s+РАБОТА", re.I),
    re.compile(r"выпускн(ая|ой)\s+квалификационн", re.I),
    re.compile(r"Прикладная\s+математика\s+и\s+информатика", re.I),
    re.compile(r"Основная\s+образовательная\s+программа", re.I),
    re.compile(r"Москва\s+20\d{2}", re.I),
    re.compile(r"(?m)^\s*на\s+тему\s*$", re.I),
)

_HSE_TITLE_HINTS_EN: tuple[re.Pattern[str], ...] = (
    re.compile(r"National Research University", re.I),
    re.compile(r"Higher School of Economics", re.I),
    re.compile(r"FACULTY OF COMPUTER SCIENCE", re.I),
    re.compile(r"GRADUATE QUALIFICATION WORK", re.I),
    re.compile(r"Government of Russian Federation", re.I),
    re.compile(r"FEDERAL STATE", re.I),
)


def _hse_title_head_likely(head: str) -> bool:
    ru = sum(1 for p in _HSE_TITLE_HINTS_RU if p.search(head))
    en = sum(1 for p in _HSE_TITLE_HINTS_EN if p.search(head))
    return ru >= 2 or en >= 2


def strip_leading_hse_title_block(text: str) -> str:
    """
    Если в начале распознан шаблон титула НИУ ВШЭ/ФКН (или англ. вариант), обрезать всё до первой строки,
    совпадающей с началом основного текста (как ``_BODY_START`` в ``vkr_text``).

    Применяется только в этом модуле (датасет публикаций ВШЭ), не в общем веб-препроцессинге.
    """
    lines = text.split("\n")
    if len(lines) < 6:
        return text
    head = "\n".join(lines[: min(120, len(lines))])
    if not _hse_title_head_likely(head):
        return text
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if _BODY_START.match(s):
            return "\n".join(lines[i:]).strip()
    return text

# --- Только ВШЭ: цифры в начале имени, затем "_" и название ---
_FILENAME_RE = re.compile(r"^(\d+)_(.+)$")


def parse_filename_stem(stem: str) -> tuple[str, str]:
    """
    stem — имя файла без расширения. Возвращает (id, title).
    """
    m = _FILENAME_RE.match(stem.strip())
    if not m:
        raise ValueError(f"Имя файла не подходит под шаблон <цифры>_<название>: {stem!r}")
    return m.group(1), m.group(2).strip()


def process_document(path: Path) -> dict[str, str | None]:
    doc_id, title = parse_filename_stem(path.stem)
    raw = load_document_text(path)
    parts = clean_thesis_text(raw)
    body = parts.get("text") or ""
    parts["text"] = strip_leading_hse_title_block(body)
    return {
        "id": doc_id,
        "title": title,
        **parts,
    }


def init_sqlite_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                abstract_ru TEXT,
                abstract_en TEXT,
                text TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_work(
    db_path: Path,
    row: dict[str, str | None],
    *,
    replace: bool = True,
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        op = "INSERT OR REPLACE" if replace else "INSERT"
        conn.execute(
            f"""
            {op} INTO works (id, title, abstract_ru, abstract_en, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["title"],
                row["abstract_ru"],
                row["abstract_en"],
                row["text"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def write_txt(out_dir: Path, row: dict[str, str | None]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{row['id']}.txt"
    p.write_text(str(row["text"]), encoding="utf-8")


def iter_source_files(
    input_dir: Path,
    *,
    extensions: tuple[str, ...] = (".pdf", ".docx", ".rtf", ".odt", ".txt"),
) -> list[Path]:
    files: list[Path] = []
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in extensions:
            files.append(p)
    return files


def run_pipeline(
    input_dir: Path,
    db_path: Path,
    txt_out_dir: Path,
    *,
    on_file: Callable[[Path, dict[str, str | None]], None] | None = None,
) -> list[dict[str, str | None]]:
    init_sqlite_db(db_path)
    rows: list[dict[str, str | None]] = []
    for path in iter_source_files(input_dir):
        try:
            row = process_document(path)
        except ValueError as e:
            print(f"SKIP {path.name}: {e}")
            continue
        insert_work(db_path, row)
        write_txt(txt_out_dir, row)
        rows.append(row)
        if on_file:
            on_file(path, row)
        else:
            print(f"OK {path.name} -> id={row['id']}")
    return rows


def strip_hse_title_from_stored(
    db_path: Path,
    txt_dir: Path,
    *,
    dry_run: bool = False,
    strip_hse_title: bool = True,
    strip_bibliography: bool = False,
) -> dict[str, int]:
    """
    Повторно применяет к уже сохранённым ``works.text`` и файлам ``txt_dir/<id>.txt`` (без PDF):

    - при ``strip_hse_title=True`` — ``strip_leading_hse_title_block`` (типовой титул НИУ ВШЭ/ФКН);
    - при ``strip_bibliography=True`` — ``strip_trailing_bibliography_section`` (список литературы / источников).

    Возвращает счётчики: ``updated``, ``unchanged``, ``txt_missing``.
    """
    if not db_path.is_file():
        raise FileNotFoundError(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        rows = list(conn.execute("SELECT id, text FROM works"))
        updated = unchanged = txt_missing = 0
        pending: list[tuple[str, str]] = []
        for work_id, text in rows:
            if text is None:
                unchanged += 1
                continue
            new_text = text
            if strip_hse_title:
                new_text = strip_leading_hse_title_block(new_text)
            if strip_bibliography:
                new_text = strip_trailing_bibliography_section(new_text)
            if new_text == text:
                unchanged += 1
                continue
            updated += 1
            if dry_run:
                print(f"would update id={work_id} ({len(text)} -> {len(new_text)} chars)")
                continue
            pending.append((work_id, new_text))
        if not dry_run and pending:
            for work_id, new_text in pending:
                conn.execute("UPDATE works SET text = ? WHERE id = ?", (new_text, work_id))
            conn.commit()
            for work_id, new_text in pending:
                out = txt_dir / f"{work_id}.txt"
                if out.is_file():
                    out.write_text(new_text, encoding="utf-8")
                else:
                    txt_missing += 1
                    print(f"warning: no txt for id={work_id} ({out})")
    finally:
        conn.close()

    return {"updated": updated, "unchanged": unchanged, "txt_missing": txt_missing}


def _cli() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Датасет ВШЭ. По умолчанию справка. "
            "Флаги постобработки уже сохранённых works + txt без PDF: "
            "--strip-hse-title, --strip-bibliography."
        )
    )
    p.add_argument(
        "--strip-hse-title",
        action="store_true",
        help="Обрезка типового титула НИУ ВШЭ в начале текста",
    )
    p.add_argument(
        "--strip-bibliography",
        action="store_true",
        help="Обрезка хвоста от заголовка «Список источников» / «Список литературы» и аналогов",
    )
    p.add_argument(
        "--db-path",
        type=Path,
        default=PROJECT_ROOT / "data/main-domain/thesis.db",
    )
    p.add_argument(
        "--txt-dir",
        type=Path,
        default=PROJECT_ROOT / "data/main-domain/txt",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, какие id изменились бы",
    )
    args = p.parse_args()
    if not (args.strip_hse_title or args.strip_bibliography):
        p.print_help()
        sys.exit(0)
    stats = strip_hse_title_from_stored(
        args.db_path,
        args.txt_dir,
        dry_run=args.dry_run,
        strip_hse_title=args.strip_hse_title,
        strip_bibliography=args.strip_bibliography,
    )
    print(stats)


if __name__ == "__main__":
    _cli()
