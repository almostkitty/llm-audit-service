"""
Разбор и очистка сырого текста ВКР (информатика, ФКН-стиль): рефераты, введение+главы, фильтр артефактов.

Используется **веб-сервисом** после извлечения текста из документа. Имя файла не используется.

Помимо базовых эвристик: склейка PDF-переносов (``-\\n``), расширенные заголовки конца текста
(список источников, библиография, варианты заключения), номера страниц в виде «стр. N» / «- N -»,
строки только из URL, линии-разделители, подписи листингов, строки с множеством ``|``/табов (хвосты таблиц),
**вырезание фрагментов, похожих на код** (огороженные блоки ```, ключевые слова, плотность ``{};``).

Срез типового титула НИУ ВШЭ для батча публикаций — только в ``extra/thesis_dataset.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.ingestion.docx_reader import extract_text_from_docx
from app.services.ingestion.odt_reader import extract_text_from_odt
from app.services.ingestion.pdf_reader import extract_text_from_pdf
from app.services.ingestion.rtf_reader import extract_text_from_rtf


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    p = str(path.resolve())
    if suffix == ".pdf":
        return extract_text_from_pdf(p)
    if suffix == ".docx":
        return extract_text_from_docx(p)
    if suffix == ".rtf":
        return extract_text_from_rtf(p)
    if suffix == ".odt":
        return extract_text_from_odt(p)
    if suffix in (".txt", ".text"):
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Неподдерживаемый формат: {suffix}")


def _norm_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def merge_hyphenated_linebreaks(text: str) -> str:
    """
    Склейка переносов из PDF/DOCX: «слово-\\nпродолжение» и мягкий перенос U+00AD.
    """
    text = text.replace("\u00ad\n", "")
    text = text.replace("\u00ad", "")
    return re.sub(r"([а-яёА-ЯЁa-zA-Z])-\n([а-яёА-ЯЁa-zA-Z])", r"\1\2", text)


_ABSTRACT_BOUNDARY = re.compile(
    r"(?is)^\s*(содержание|оглавление|введение|introduction|"
    r"глава\s*(1|i|I|первая)|chapter\s*1|"
    r"реферат|аннотация|abstract|summary|"
    r"ключевые\s+слова|keywords)\s*:?\s*$"
)

_REF_RU_START = re.compile(
    r"(?i)^\s*(реферат|аннотация)\s*:?\s*$"
)
_REF_EN_START = re.compile(
    r"(?i)^\s*(abstract|summary)\s*:?\s*$"
)


def _collect_section(lines: list[str], start_idx: int, boundary: re.Pattern[str]) -> tuple[str, int]:
    buf: list[str] = []
    i = start_idx
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped and boundary.match(stripped):
            break
        buf.append(line)
        i += 1
    text = "\n".join(buf).strip()
    return text, i


def extract_abstract_sections(raw: str) -> tuple[str | None, str | None]:
    text = _norm_newlines(raw)
    lines = text.split("\n")

    abstract_ru: str | None = None
    abstract_en: str | None = None

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if abstract_ru is None and _REF_RU_START.match(stripped):
            block, next_i = _collect_section(lines, i + 1, _ABSTRACT_BOUNDARY)
            if block:
                abstract_ru = block
            i = next_i
            continue
        if abstract_en is None and _REF_EN_START.match(stripped):
            block, next_i = _collect_section(lines, i + 1, _ABSTRACT_BOUNDARY)
            if block:
                abstract_en = block
            i = next_i
            continue
        i += 1

    return abstract_ru, abstract_en


# Начало основного текста: «Введение» с/без номера и с продолжением в строке; «Глава 1» — с заголовком.
_BODY_START = re.compile(
    r"^(введение|introduction)\s*$|"
    r"^\d+\.?\s+(введение|introduction)\s*$|"
    r"^(введение|introduction)\s+\S.*$|"
    r"^(глава\s*(1|i|I|первая)|chapter\s*1)\b.*$|"
    r"^(chapter\s+one|часть\s*1)\s*$",
    re.IGNORECASE,
)

# Конец основного текста — строка целиком (иначе ложное «заключение» внутри фразы).
# Библиография: «Список источников», «Список литературы», с/без нумерации («6. …»), с «:» в конце строки.
_BIB_HEAD_LINE = re.compile(
    r"(?i)^(?:"
    r"(?:\d{1,2}\s*[.)]\s*)?"
    r"(?:"
    r"список\s+(?:использованной\s+|использованных\s+)?(?:литературы|источников|публикаций|публикации)\b|"
    r"список\s+литературы\b|"
    r"список\s+источников\b|"
    r"использованн(?:ая|ые)\s+литератур(?:а|ы)\b|"
    r"библиографи(?:ческий\s+список|я)\b|"
    r"references?\b|bibliograph(?:y|ical)\b"
    r")"
    r")\s*[:.;–\-]?\s*$"
)

_BODY_END = re.compile(
    r"(?i)^(заключение|conclusion)\s*$|"
    r"^(итоги?|summary\s+and\s+conclusion)\s*$|"
    + _BIB_HEAD_LINE.pattern[4:]  # без (?i) — флаг уже в начале шаблона
    + r"|^(приложени(е|я)|обозначени(е|я)|notation|appendix|сокращени(е|я))\s*$"
)


def slice_main_chapters(raw: str) -> str:
    text = _norm_newlines(raw)
    lines = text.split("\n")
    start_i: int | None = None
    end_i: int | None = None

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if start_i is None and _BODY_START.match(s):
            start_i = i
            continue
        if start_i is not None and end_i is None and _BODY_END.match(s):
            end_i = i
            break

    if start_i is None:
        start_i = 0
    if end_i is None:
        end_i = len(lines)

    body = "\n".join(lines[start_i:end_i]).strip()
    return body


def strip_trailing_bibliography_section(text: str) -> str:
    """
    Удаляет хвост от заголовка списка литературы / источников (см. ``_BIB_HEAD_LINE``).

    Берётся **последнее** совпадение: в начале текста то же «8. Библиография» часто встречается в
    оглавлении; реальный раздел обычно в конце.
    """
    text = _norm_newlines(text)
    lines = text.split("\n")
    cut: int | None = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if _BIB_HEAD_LINE.match(s):
            cut = i
    if cut is None:
        return text
    return "\n".join(lines[:cut]).strip()


def strip_code_like_blocks(text: str) -> str:
    """
    Удаление фрагментов, похожих на код (листинги в ВКР по информатике), чтобы не раздувать метрики.

    Эвристики: блоки между строками `` ``` `` (как в разметке), строки с типичными ключевыми словами,
    строки с высокой плотностью символов ``{};()`` при малой доле кириллицы. Блоки по отступам не режем —
    чтобы не срезать цитаты/примеры с пробелами.
    """
    text = _strip_markdown_code_fences(text)
    out_lines: list[str] = []
    for line in text.split("\n"):
        if _is_probable_code_line(line):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _strip_markdown_code_fences(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


# Типичные старты строк кода (ВКР ФКН: Python/Java/JS/SQL/C и т.д.)
_CODE_KW = re.compile(
    r"(?i)^[\s\u00a0]*("
    r"\bdef\s+\w|\bclass\s+\w|@\w+\s*$|"
    r"\bfrom\s+\w+\s+import\s|\bimport\s+\w|"
    r"#include\s*[<\"]|"
    r"\bpackage\s+|"
    r"\bpublic\s+(class|static|void|interface|abstract)|"
    r"\bprivate\s+(static\s+)?|"
    r"\bprotected\s+|"
    r"\bstatic\s+void\s+main\b|"
    r"\bfunction\s+[\w$]|\bfunction\s*\(|\bconsole\.|"
    r"\b(const|let|var)\s+\w|=>|"
    r"\bSELECT\s+|\bINSERT\s+INTO|\bUPDATE\s+\w+\s+SET|\bDELETE\s+FROM|\bCREATE\s+TABLE|"
    r"<\?php|<!DOCTYPE|</?script\b|"
    r"\bfn\s+\w|\bimpl\s+|trait\s+\w|\bpub\s+fn\b"
    r")"
)


def _cyrillic_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    cy = sum(1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё")
    return cy / len(letters)


def _code_symbol_density(s: str) -> float:
    if not s.strip():
        return 0.0
    code_chars = sum(1 for c in s if c in "{}[];()=<>+-*|&`~\\/")
    return code_chars / len(s)


_ORPHAN_STMT = re.compile(
    r"(?i)^[\s\u00a0]*("
    r"return\s+|yield\s+|pass\s*$|"
    r"break\s*$|continue\s*$|"
    r"else\s*:|elif\s+|except\s+|finally\s*:"
    r")"
)


def _is_probable_code_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 4:
        return False
    if _CODE_KW.match(line):
        return True
    if _ORPHAN_STMT.match(line) and _cyrillic_ratio(s) < 0.25:
        return True
    # Строка с «программистской» пунктуацией и мало кириллицы (не обычное предложение)
    if len(s) >= 24 and _code_symbol_density(s) >= 0.14 and _cyrillic_ratio(s) < 0.35:
        return True
    # Типичная однострочная присваивание/вызов в стиле C/Java/JS
    if (
        s.endswith(";")
        and "=" in s
        and "(" in s
        and _cyrillic_ratio(s) < 0.2
        and len(s) < 200
    ):
        return True
    return False


_PAGE_ONLY = re.compile(r"^\s*\d{1,4}\s*$")
# «- 12 -», «— 5 —»
_PAGE_DASH_NUM = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")
# стр. 5, Page 12, Лист 3
_PAGE_WORD = re.compile(r"(?i)^\s*(стр\.?|page|лист(ов)?)\s*[:]?\s*\d{1,4}\s*$")
_CAPTION = re.compile(r"(?i)^(рисунок|рис\.|таблица|табл\.)\s*[\d\.\s\-–]+")
# Подпись к листингу
_LISTING = re.compile(r"(?i)^(листинг|listing)\s*[\d\.\s\-–:]+")
_FORMULAISH = re.compile(r"^[+\-*/=()\d\s]{6,}$")
_URL_ONLY = re.compile(r"(?i)^https?://\S+$")
# Разделители страниц в PDF
_RULE_LINE = re.compile(r"^\s*[-–—_=]{4,}\s*$")


def clean_artifacts(text: str) -> str:
    out_lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out_lines.append("")
            continue
        if _PAGE_ONLY.match(s) and len(s) <= 4:
            continue
        if _PAGE_DASH_NUM.match(s):
            continue
        if _PAGE_WORD.match(s):
            continue
        if _CAPTION.match(s):
            continue
        if _LISTING.match(s):
            continue
        if _FORMULAISH.match(s):
            continue
        if _URL_ONLY.match(s):
            continue
        if _RULE_LINE.match(s):
            continue
        # Хвосты таблиц из PDF: много «|» или табуляций в строке
        if s.count("|") >= 4 or s.count("\t") >= 4:
            continue
        out_lines.append(line.rstrip())
    collapsed: list[str] = []
    prev_empty = False
    for line in out_lines:
        empty = not line.strip()
        if empty and prev_empty:
            continue
        collapsed.append(line)
        prev_empty = empty
    return "\n".join(collapsed).strip()


def clean_thesis_text(raw: str) -> dict[str, str | None]:
    """
    Сырой текст документа → ``abstract_ru``, ``abstract_en``, очищенное ``text`` (введение и главы).
    """
    raw = _norm_newlines(raw)
    raw = merge_hyphenated_linebreaks(raw)
    abstract_ru, abstract_en = extract_abstract_sections(raw)
    body = slice_main_chapters(raw)
    body = strip_trailing_bibliography_section(body)
    body = strip_code_like_blocks(body)
    body = clean_artifacts(body)
    return {
        "abstract_ru": abstract_ru,
        "abstract_en": abstract_en,
        "text": body,
    }
