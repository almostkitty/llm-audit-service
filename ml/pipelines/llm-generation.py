"""
Генерация синтетических ВКР через DeepSeek API по данным из SQLite ``works``.

Для каждой строки ``works`` с непустой русской или английской аннотацией строится промпт
(``title`` + аннотация), вызывается API, результат сохраняется:

- таблица ``llm_works`` в том же файле БД (логическое имя «llm-works»: без дефиса в SQL);
- файл ``data/main-domain/llm-txt/<work_id>.txt``.

Строки без аннотации пропускаются, запрос к API не отправляется.

**Продолжение после сбоя:** запусти снова с ``--skip-existing`` — будут пропущены работы,
для которых уже есть файл ``llm-txt/<id>.txt`` или запись в ``llm_works`` (если файл потерян,
текст подтянется из БД). Остальные обработаются с той же очереди.

**Скорость:** у DeepSeek лимиты динамические; параллельные запросы допускаются (``--workers``).
**Объём ответа:** для ~2500 слов по-русски нужно порядка 6K+ токенов вывода; при лимите 4K ответ часто обрывается около ~1.7K слов — см. ``--max-tokens`` (по умолчанию 8192).
При обрыве по лимите вывода API (``finish_reason=length``) делаются дополнительные запросы-продолжения — см. ``--max-completion-rounds``.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

DEFAULT_DB_PATH = PROJECT_ROOT / "data/main-domain/thesis.db"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data/main-domain/llm-txt"


# --- env / API -----------------------------------------------------------------


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_api_key() -> str:
    load_env_file(ENV_PATH)
    for name in ("API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        v = os.getenv(name)
        if v:
            return v
    raise RuntimeError("Задай API_KEY или DEEPSEEK_API_KEY в .env")


def _ssl_context_for_https(ca_bundle: str | None, insecure: bool) -> ssl.SSLContext | None:
    """
    macOS / часть установок Python не подхватывают системные CA → CERTIFICATE_VERIFY_FAILED.
    По умолчанию используем ``certifi`` (после ``pip install -r requirements.txt``).
    """
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _finish_reason(raw: dict) -> str:
    try:
        fr = raw["choices"][0].get("finish_reason")
        return (fr or "").strip().lower()
    except (KeyError, IndexError, TypeError):
        return ""


_CONTINUE_USER = (
    "Продолжи текст выпускной работы сразу с того места, на котором оборвался предыдущий ответ. "
    "Не повторяй уже написанное; выведи только продолжение, без пояснений."
)


def call_deepseek_messages(
    *,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    ca_bundle: str | None,
    insecure_tls: bool = False,
) -> tuple[str, dict]:
    api_key = resolve_api_key()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        DEEPSEEK_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    ctx = _ssl_context_for_https(ca_bundle, insecure_tls)
    try:
        with request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(
            f"DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Сеть: {exc.reason}") from exc

    try:
        content = data["choices"][0]["message"].get("content")
        text = (content or "").strip()
        return text, data
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Неожиданный ответ API: {data}") from exc


def call_deepseek(
    *,
    prompt: str,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
    ca_bundle: str | None,
    insecure_tls: bool = False,
) -> tuple[str, dict]:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    return call_deepseek_messages(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        ca_bundle=ca_bundle,
        insecure_tls=insecure_tls,
    )


def deepseek_generate_until_complete(
    *,
    prompt: str,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
    max_completion_rounds: int,
    ca_bundle: str | None,
    insecure_tls: bool = False,
) -> tuple[str, dict]:
    """
    Повторяет запросы, пока ``finish_reason`` не ``stop`` (или пока не исчерпан лимит раундов).

    Если ответ оборван по лимиту вывода (обычно ``finish_reason == "length"``), добавляется раунд
    продолжения в том же диалоге — текст склеивается без разрыва между частями.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    parts: list[str] = []
    last_raw: dict = {}
    raws: list[dict] = []
    rounds = max(1, max_completion_rounds)
    for r in range(rounds):
        chunk, last_raw = call_deepseek_messages(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            ca_bundle=ca_bundle,
            insecure_tls=insecure_tls,
        )
        raws.append(last_raw)
        parts.append(chunk)
        fr = _finish_reason(last_raw)
        if fr != "length":
            break
        if r + 1 >= rounds:
            break
        messages.append({"role": "assistant", "content": chunk})
        messages.append({"role": "user", "content": _CONTINUE_USER})
    full = "".join(parts).strip()
    if len(raws) == 1:
        meta = last_raw
    else:
        meta = {
            "multi_round": True,
            "rounds": len(raws),
            "finish_reason_last": _finish_reason(last_raw),
            "responses": raws,
        }
    return full, meta


# --- SQLite: llm_works + works -------------------------------------------------


def ensure_llm_works_table(conn: sqlite3.Connection) -> None:
    # Исторически таблица создавалась с UNIQUE(work_id), из-за чего повторная генерация
    # с другой temperature перезаписывала старую запись. Здесь поддерживаем "append-only":
    # один work_id может иметь несколько LLM-версий.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT NOT NULL,
            title TEXT NOT NULL,
            abstract TEXT NOT NULL,
            generated_text TEXT NOT NULL,
            model TEXT NOT NULL,
            temperature REAL NOT NULL,
            max_tokens INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # Миграция старой схемы (UNIQUE(work_id)) -> новая (без UNIQUE).
    # В sqlite автоиндексы для UNIQUE часто имеют sql = NULL, поэтому проверяем через PRAGMA.
    has_unique_work_id = False
    for _, idx_name, is_unique, *_ in conn.execute("PRAGMA index_list('llm_works')"):
        if int(is_unique) != 1:
            continue
        cols = [row[2] for row in conn.execute(f"PRAGMA index_info('{idx_name}')")]
        if cols == ["work_id"]:
            has_unique_work_id = True
            break
    if has_unique_work_id:
        conn.execute("DROP TABLE IF EXISTS llm_works_v2")
        conn.execute(
            """
            CREATE TABLE llm_works_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id TEXT NOT NULL,
                title TEXT NOT NULL,
                abstract TEXT NOT NULL,
                generated_text TEXT NOT NULL,
                model TEXT NOT NULL,
                temperature REAL NOT NULL,
                max_tokens INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO llm_works_v2 (
                work_id, title, abstract, generated_text, model, temperature, max_tokens, created_at
            )
            SELECT work_id, title, abstract, generated_text, model, temperature, max_tokens, created_at
            FROM llm_works
            ORDER BY id
            """
        )
        conn.execute("DROP TABLE llm_works")
        conn.execute("ALTER TABLE llm_works_v2 RENAME TO llm_works")
    conn.commit()


def upsert_llm_work(
    conn: sqlite3.Connection,
    *,
    work_id: str,
    title: str,
    abstract: str,
    generated_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    created_at: str,
) -> None:
    # Специально без upsert: одинаковый work_id с разной temperature должен храниться
    # отдельными строками для расширения датасета.
    conn.execute(
        """
        INSERT INTO llm_works (
            work_id, title, abstract, generated_text,
            model, temperature, max_tokens, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            work_id,
            title,
            abstract,
            generated_text,
            model,
            temperature,
            max_tokens,
            created_at,
        ),
    )


def count_llm_works(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM llm_works").fetchone()[0])


def count_llm_works_for_ids(conn: sqlite3.Connection, work_ids: list[str]) -> int:
    if not work_ids:
        return 0
    ph = ",".join("?" * len(work_ids))
    q = f"SELECT COUNT(*) FROM llm_works WHERE work_id IN ({ph})"
    return int(conn.execute(q, work_ids).fetchone()[0])


def work_ids_with_llm_rows(conn: sqlite3.Connection, work_ids: list[str]) -> set[str]:
    if not work_ids:
        return set()
    ph = ",".join("?" * len(work_ids))
    q = f"SELECT work_id FROM llm_works WHERE work_id IN ({ph})"
    return {str(r[0]) for r in conn.execute(q, work_ids).fetchall()}


def fetch_generated_text_for_work(conn: sqlite3.Connection, work_id: str) -> str | None:
    row = conn.execute(
        "SELECT generated_text FROM llm_works WHERE work_id = ?", (work_id,)
    ).fetchone()
    return row[0] if row else None


def fetch_works(conn: sqlite3.Connection) -> list[dict[str, str | None]]:
    cur = conn.execute(
        "SELECT id, title, abstract_ru, abstract_en, text FROM works ORDER BY id"
    )
    return [
        {
            "id": row[0],
            "title": row[1],
            "abstract_ru": row[2],
            "abstract_en": row[3],
            "text": row[4],
        }
        for row in cur.fetchall()
    ]


def load_rows_and_llm_total(db_path: Path, limit: int) -> tuple[list[dict[str, str | None]], int]:
    with sqlite3.connect(str(db_path)) as conn:
        ensure_llm_works_table(conn)
        rows = fetch_works(conn)
        llm_total_before = count_llm_works(conn)
    if limit > 0:
        rows = rows[:limit]
    return rows, llm_total_before


def load_llm_indices(db_path: Path, ids_all: list[str]) -> tuple[int, set[str]]:
    with sqlite3.connect(str(db_path)) as conn:
        ensure_llm_works_table(conn)
        return (
            count_llm_works_for_ids(conn, ids_all),
            work_ids_with_llm_rows(conn, ids_all),
        )


# --- prompt -------------------------------------------------------------------


def _word_count(s: str) -> int:
    return len(s.split())


def pick_abstract(row: dict[str, str | None]) -> str | None:
    ru = (row.get("abstract_ru") or "").strip()
    if ru:
        return ru
    en = (row.get("abstract_en") or "").strip()
    if en:
        return en
    return None


def build_prompt(*, title: str, abstract: str, body_text: str) -> str:
    wc = _word_count(body_text or "")
    target = 2500 if wc <= 0 else max(1500, min(wc, 4500))
    lo, hi = int(target * 0.9), int(target * 1.1)
    return (
        "Сгенерируй новый оригинальный текст ВКР на русском языке.\n"
        "Требования:\n"
        "- Академический стиль, техническая направленность.\n"
        "- НЕ копируй дословно существующие тексты.\n"
        "- Структура: (1) раздел «Введение» с постановкой цели и обзором дальнейшего; "
        "(2) главы 1, 2 и 3 с содержательным текстом; после каждой из трёх глав — "
        "краткий подраздел с выводами по этой главе (несколько предложений или короткий абзац, без дублирования всей главы).\n"
        "- Без: реферата, abstract, общего заключения всей работы в конце, списка источников, приложений.\n"
        "- Связный текст, без лишних маркдаун-разметок.\n"
        f"- Объём: около {target} слов всего (допустимо {lo}–{hi}); доведи до диапазона, "
        "без обрыва на середине раздела.\n\n"
        f"Тема: {title.strip()}\n\n"
        f"Аннотация (из исходной работы):\n{abstract}\n\n"
        "Верни только текст работы."
    )


# --- batch run ----------------------------------------------------------------


@dataclass(frozen=True)
class GenConfig:
    db_path: Path
    out_dir: Path
    model: str
    temperature: float
    max_tokens: int
    max_completion_rounds: int
    system: str
    ca_bundle: str | None
    insecure_tls: bool
    skip_existing: bool
    json_out_dir: Path | None
    workers: int


def _print_preflight(
    *,
    n: int,
    limit_flag: bool,
    n_eligible: int,
    n_no_abs: int,
    llm_total_before: int,
    llm_in_selection: int,
    n_txt: int,
    txt_for_eligible: int,
    eligible_without_txt: int,
    out_dir: Path,
    skip_existing: bool,
    work_ids_in_llm: set[str],
    workers: int,
) -> None:
    print(
        "\n--- Сводка до запуска ---\n"
        f"  works в выборке: {n}"
        + (f" (--limit)" if limit_flag else "")
        + "\n"
        f"  с аннотацией (подходят под генерацию): {n_eligible}\n"
        f"  без аннотации (будут пропущены): {n_no_abs}\n"
        f"  записей в llm_works всего в БД: {llm_total_before}\n"
        f"  из них по id из этой выборки: {llm_in_selection}/{n}\n"
        f"  файлов *.txt в {out_dir}: {n_txt} "
        f"(для id с аннотацией уже есть {txt_for_eligible}/{n_eligible}, "
        f"ещё без файла: {eligible_without_txt})\n"
        + (
            f"  параллельных воркеров (--workers): {workers}\n"
            if workers > 1
            else ""
        )
        + (
            f"  режим --skip-existing: пропуск, если есть {out_dir.name}/<id>.txt "
            f"или запись в llm_works ({len(work_ids_in_llm)} id в БД по выборке)\n"
            if skip_existing
            else ""
        )
        + "---\n"
    )


def _skip_if_already_done(
    cfg: GenConfig,
    *,
    idx: int,
    n: int,
    wid: str,
    path: Path,
    work_ids_in_llm: set[str],
) -> bool:
    """Возвращает True, если строку нужно пропустить (уже есть результат)."""
    if not cfg.skip_existing:
        return False
    if path.exists():
        print(f"[{idx}/{n}] skip existing {path.name}")
        return True
    if wid not in work_ids_in_llm:
        return False
    with sqlite3.connect(str(cfg.db_path)) as conn:
        gt = fetch_generated_text_for_work(conn, wid)
    if gt is not None:
        path.write_text(gt.strip() + "\n", encoding="utf-8")
        print(f"[{idx}/{n}] skip: запись в llm_works (файл восстановлен) {path.name}")
        return True
    print(f"[{idx}/{n}] WARN: в llm_works нет текста для {wid}, повторная генерация")
    return False


def _persist_success(
    cfg: GenConfig,
    *,
    wid: str,
    title: str,
    abstract: str,
    text: str,
    raw: dict,
    io_lock: threading.Lock | None = None,
) -> None:
    def _write() -> None:
        path = cfg.out_dir / f"{wid}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with sqlite3.connect(str(cfg.db_path)) as conn:
            ensure_llm_works_table(conn)
            upsert_llm_work(
                conn,
                work_id=wid,
                title=title,
                abstract=abstract,
                generated_text=text,
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                created_at=created,
            )
            conn.commit()
        if cfg.json_out_dir:
            jp = cfg.json_out_dir / f"{wid}.json"
            jp.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    if io_lock is not None:
        with io_lock:
            _write()
    else:
        _write()


def _generate_one_work(
    cfg: GenConfig,
    *,
    idx: int,
    n: int,
    row: dict[str, str | None],
    abstract: str,
    io_lock: threading.Lock | None,
    print_lock: threading.Lock,
    session_ok: list[int],
) -> tuple[str, str, str | None]:
    """
    Один запрос к API + сохранение.
    Возвращает ``(status, work_id, error_or_none)``, ``status`` — ``ok`` или ``fail``.
    """
    wid = str(row["id"])
    title = str(row.get("title") or "")
    body = str(row.get("text") or "")
    path = cfg.out_dir / f"{wid}.txt"
    prompt = build_prompt(title=title, abstract=abstract, body_text=body)
    with print_lock:
        print(f"[{idx}/{n}] generate {wid} …")
    try:
        text, raw = deepseek_generate_until_complete(
            prompt=prompt,
            system=cfg.system,
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            max_completion_rounds=cfg.max_completion_rounds,
            ca_bundle=cfg.ca_bundle,
            insecure_tls=cfg.insecure_tls,
        )
        text = text.strip()
        _persist_success(
            cfg,
            wid=wid,
            title=title,
            abstract=abstract,
            text=text,
            raw=raw,
            io_lock=io_lock,
        )
        with print_lock:
            session_ok[0] += 1
            extra = ""
            if isinstance(raw, dict) and raw.get("multi_round"):
                extra = f" | API раундов: {raw.get('rounds')}"
            print(
                f"  → {path.name} + llm_works | успешно в сессии: {session_ok[0]}{extra}"
            )
            if (
                isinstance(raw, dict)
                and raw.get("multi_round")
                and raw.get("finish_reason_last") == "length"
            ):
                print(
                    f"  WARN {wid}: после {raw.get('rounds')} раундов ответ всё ещё length — "
                    "увеличь --max-tokens или --max-completion-rounds"
                )
        return ("ok", wid, None)
    except Exception as exc:  # noqa: BLE001
        with print_lock:
            print(f"  ERROR {wid}: {exc}")
        return ("fail", wid, str(exc))


def _print_postflight(
    *,
    dt: float,
    ok: int,
    skip_abs: int,
    skip_file: int,
    fail: int,
    llm_total_before: int,
    llm_total_after: int,
    llm_in_selection: int,
    llm_in_selection_after: int,
    n_eligible: int,
    n_txt: int,
    n_txt_after: int,
    txt_for_eligible: int,
    txt_for_eligible_after: int,
    out_dir_name: str,
) -> None:
    print(
        f"\n--- Итог за {dt:.1f}s ---\n"
        f"  API успешно (записей в llm_works за сессию): {ok}\n"
        f"  пропуск без аннотации: {skip_abs}\n"
        f"  пропуск (--skip-existing): {skip_file}\n"
        f"  ошибок API: {fail}\n"
        f"  llm_works в БД всего: {llm_total_before} → {llm_total_after}\n"
        f"  llm_works по id из этой выборки: {llm_in_selection} → {llm_in_selection_after} "
        f"(из {n_eligible} с аннотацией)\n"
        f"  файлов в {out_dir_name}: {n_txt} → {n_txt_after} "
        f"(для id с аннотацией: {txt_for_eligible} → {txt_for_eligible_after}/{n_eligible})\n"
        "---\n"
    )


def run_generation(cfg: GenConfig, *, limit_arg: int) -> None:
    rows, llm_total_before = load_rows_and_llm_total(cfg.db_path, limit_arg)
    n = len(rows)
    ids_all = [str(r["id"]) for r in rows]
    eligible_rows = [r for r in rows if pick_abstract(r) is not None]
    n_eligible = len(eligible_rows)
    n_no_abs = n - n_eligible
    eligible_ids = [str(r["id"]) for r in eligible_rows]

    llm_in_selection, work_ids_in_llm = load_llm_indices(cfg.db_path, ids_all)

    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    if cfg.json_out_dir:
        cfg.json_out_dir.mkdir(parents=True, exist_ok=True)

    n_txt = len(list(cfg.out_dir.glob("*.txt")))
    txt_for_eligible = sum(
        1 for wid in eligible_ids if (cfg.out_dir / f"{wid}.txt").is_file()
    )
    eligible_without_txt = max(0, n_eligible - txt_for_eligible)

    _print_preflight(
        n=n,
        limit_flag=bool(limit_arg),
        n_eligible=n_eligible,
        n_no_abs=n_no_abs,
        llm_total_before=llm_total_before,
        llm_in_selection=llm_in_selection,
        n_txt=n_txt,
        txt_for_eligible=txt_for_eligible,
        eligible_without_txt=eligible_without_txt,
        out_dir=cfg.out_dir,
        skip_existing=cfg.skip_existing,
        work_ids_in_llm=work_ids_in_llm,
        workers=cfg.workers,
    )

    ok = skip_abs = skip_file = fail = 0
    t0 = time.perf_counter()

    pending: list[tuple[int, dict[str, str | None], str]] = []
    for i, row in enumerate(rows, 1):
        wid = str(row["id"])
        abstract = pick_abstract(row)
        if abstract is None:
            skip_abs += 1
            print(f"[{i}/{n}] SKIP {wid}: нет аннотации")
            continue

        path = cfg.out_dir / f"{wid}.txt"
        if _skip_if_already_done(
            cfg,
            idx=i,
            n=n,
            wid=wid,
            path=path,
            work_ids_in_llm=work_ids_in_llm,
        ):
            skip_file += 1
            continue

        pending.append((i, row, abstract))

    session_ok: list[int] = [0]
    print_lock = threading.Lock()
    io_lock = threading.Lock() if cfg.workers > 1 else None

    if pending:
        if cfg.workers <= 1:
            for i, row, abstract in pending:
                st, _, _ = _generate_one_work(
                    cfg,
                    idx=i,
                    n=n,
                    row=row,
                    abstract=abstract,
                    io_lock=None,
                    print_lock=print_lock,
                    session_ok=session_ok,
                )
                if st == "ok":
                    ok += 1
                else:
                    fail += 1
        else:
            with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
                futures = [
                    pool.submit(
                        _generate_one_work,
                        cfg,
                        idx=i,
                        n=n,
                        row=row,
                        abstract=abstract,
                        io_lock=io_lock,
                        print_lock=print_lock,
                        session_ok=session_ok,
                    )
                    for i, row, abstract in pending
                ]
                for fut in as_completed(futures):
                    st, _, _ = fut.result()
                    if st == "ok":
                        ok += 1
                    else:
                        fail += 1

    with sqlite3.connect(str(cfg.db_path)) as conn:
        llm_total_after = count_llm_works(conn)
        llm_in_selection_after = count_llm_works_for_ids(conn, ids_all)

    n_txt_after = len(list(cfg.out_dir.glob("*.txt")))
    txt_for_eligible_after = sum(
        1 for wid in eligible_ids if (cfg.out_dir / f"{wid}.txt").is_file()
    )
    dt = time.perf_counter() - t0

    _print_postflight(
        dt=dt,
        ok=ok,
        skip_abs=skip_abs,
        skip_file=skip_file,
        fail=fail,
        llm_total_before=llm_total_before,
        llm_total_after=llm_total_after,
        llm_in_selection=llm_in_selection,
        llm_in_selection_after=llm_in_selection_after,
        n_eligible=n_eligible,
        n_txt=n_txt,
        n_txt_after=n_txt_after,
        txt_for_eligible=txt_for_eligible,
        txt_for_eligible_after=txt_for_eligible_after,
        out_dir_name=cfg.out_dir.name,
    )


def parse_args() -> tuple[GenConfig, int]:
    p = argparse.ArgumentParser(
        description="DeepSeek: генерация текстов по works → llm_works + llm-txt/"
    )
    p.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite с таблицей works (по умолчанию {DEFAULT_DB_PATH})",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Каталог для {DEFAULT_OUT_DIR.name}/<id>.txt",
    )
    p.add_argument("--model", default="deepseek-chat")
    p.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help=(
            "Параметр сэмплирования API (по умолчанию 1.0, как в документации DeepSeek). "
            "Ориентиры: код/математика — 0.0; анализ/данные — 1.0; диалог — 1.3; творчество — 1.5. "
            "Для связного академического текста обычно достаточно 1.0 или чуть ниже."
        ),
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help=(
            "Лимит токенов ответа. Для русского текста ~2500 слов нужно ~6K+ токенов; при 4K вывод "
            "часто обрывается около 1.7K слов. У DeepSeek-V3 Chat типично до 8K на вывод."
        ),
    )
    p.add_argument(
        "--max-completion-rounds",
        type=int,
        default=10,
        help=(
            "Максимум запросов к API подряд для одной работы. Если ответ оборван по лимиту токенов "
            "(finish_reason=length), отправляется продолжение. Значение 1 отключает автопродолжение."
        ),
    )
    p.add_argument("--limit", type=int, default=0, help="Обработать только первые N (0 = все)")
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Число параллельных запросов к API (по умолчанию 1). "
            "Провайдер допускает наращивание параллелизма; начни с 2–4 и смотри на ошибки 429/троттлинг."
        ),
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Пропускать генерацию, если результат уже есть: файл llm-txt/<id>.txt "
            "или строка в llm_works (удобно продолжать после обрыва; при отсутствии файла "
            "текст восстанавливается из БД)."
        ),
    )
    p.add_argument(
        "--system",
        default="Ты пишешь связный академический текст на русском языке.",
    )
    p.add_argument(
        "--ca-bundle",
        default=os.getenv("SSL_CERT_FILE"),
        help="Явный PEM с CA; иначе используется пакет certifi (см. requirements.txt).",
    )
    p.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Отключить проверку TLS (только если нет другого выхода; небезопасно).",
    )
    p.add_argument(
        "--json-out-dir",
        type=Path,
        default=None,
        help="Сохранять сырой JSON ответа API в каталог",
    )
    args = p.parse_args()
    ca_bundle = args.ca_bundle if args.ca_bundle else None
    workers = max(1, args.workers)
    cfg = GenConfig(
        db_path=args.db_path,
        out_dir=args.out_dir,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_completion_rounds=max(1, args.max_completion_rounds),
        system=args.system,
        ca_bundle=ca_bundle,
        insecure_tls=args.insecure_skip_tls_verify,
        skip_existing=args.skip_existing,
        json_out_dir=args.json_out_dir,
        workers=workers,
    )
    return cfg, args.limit


def main() -> None:
    cfg, limit_arg = parse_args()
    if not cfg.db_path.is_file():
        raise SystemExit(f"База не найдена: {cfg.db_path}")
    run_generation(cfg, limit_arg=limit_arg)


if __name__ == "__main__":
    main()
