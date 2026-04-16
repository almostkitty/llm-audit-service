import argparse
import json
import os
import ssl
import time
from pathlib import Path
from dataclasses import dataclass
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TEXT_DATA = PROJECT_ROOT / "data/works/manual_2018/text-data.txt"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data/works/manual_2018/llm"


@dataclass
class WorkItem:
    file_name: str
    title: str
    abstract_ru: str
    chapters: list[str]
    human_words: int


def load_env_file(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE)."""
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
    """Supports API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY."""
    load_env_file(ENV_PATH)
    for key_name in ("API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        value = os.getenv(key_name)
        if value:
            return value
    raise RuntimeError(
        "API key not found. Set API_KEY (or DEEPSEEK_API_KEY) in .env."
    )


def call_deepseek(
    *,
    prompt: str,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
    ca_bundle: str | None = None,
) -> tuple[str, dict]:
    api_key = resolve_api_key()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
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

    context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else None

    try:
        with request.urlopen(req, timeout=120, context=context) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        text = response_data["choices"][0]["message"]["content"].strip()
        return text, response_data
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected API response: {response_data}") from exc


def parse_text_data(path: Path) -> list[WorkItem]:
    """
    Parse blocks like:
      #file: text1.txt
      #title: ...
      #abstract-ru: ...
      #chapters:
      ...
      #human-words: 2195
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    items: list[WorkItem] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("#file:"):
            i += 1
            continue

        file_name = line.split(":", 1)[1].strip()
        title = ""
        abstract_ru = ""
        chapters: list[str] = []
        human_words = 0

        i += 1
        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            if stripped.startswith("#file:"):
                break

            if stripped.startswith("#title:"):
                title = stripped.split(":", 1)[1].strip()
                i += 1
                continue

            if stripped.startswith("#abstract-ru:"):
                first = stripped.split(":", 1)[1].strip()
                abstract_parts = [first] if first else []
                i += 1
                while i < len(lines):
                    nxt = lines[i].strip()
                    if nxt.startswith("#"):
                        break
                    if nxt:
                        abstract_parts.append(nxt)
                    i += 1
                abstract_ru = " ".join(abstract_parts).strip()
                continue

            if stripped.startswith("#chapters:"):
                i += 1
                while i < len(lines):
                    nxt = lines[i].strip()
                    if nxt.startswith("#"):
                        break
                    if nxt:
                        chapters.append(nxt)
                    i += 1
                continue

            if stripped.startswith("#human-words:"):
                value = stripped.split(":", 1)[1].strip()
                try:
                    human_words = int(value)
                except ValueError:
                    human_words = 0
                i += 1
                continue

            i += 1

        items.append(
            WorkItem(
                file_name=file_name,
                title=title,
                abstract_ru=abstract_ru,
                chapters=chapters,
                human_words=human_words,
            )
        )

    return items


def build_prompt(item: WorkItem) -> str:
    forbidden_markers = (
        "реферат",
        "abstract",
        "введение",
        "заключение",
        "список",
        "библиограф",
        "приложен",
        "содержание",
    )
    content_chapters = [
        c for c in item.chapters if not any(marker in c.lower() for marker in forbidden_markers)
    ]
    chapters_block = (
        "\n".join(f"- {c}" for c in content_chapters[:20]) if content_chapters else "- Главы 1-3 (содержательная часть)"
    )
    target_words = item.human_words if item.human_words > 0 else 2500
    min_words = int(target_words * 0.9)
    max_words = int(target_words * 1.1)

    return (
        "Сгенерируй новый оригинальный текст ВКР на русском языке.\n"
        "Требования:\n"
        "- Академический стиль, техническая направленность.\n"
        "- НЕ копируй и НЕ перефразируй дословно существующие тексты.\n"
        "- Пиши только содержательную часть глав 1-3.\n"
        "- НЕ добавляй разделы: Реферат, Abstract, Введение, Заключение, Список источников, Приложения.\n"
        "- Избегай клишированных вводных формул и лишних списков; нужен связный основной текст.\n"
        f"- Целевой объем: {target_words} слов (допуск: {min_words}..{max_words}).\n\n"
        f"Тема: {item.title}\n\n"
        f"Аннотация (RU): {item.abstract_ru}\n\n"
        "Ориентир по структуре содержательных разделов:\n"
        f"{chapters_block}\n\n"
        "Верни только текст работы, без пояснений и без markdown."
    )


def generate_one(
    *,
    item: WorkItem,
    system: str,
    model: str,
    temperature: float,
    max_tokens: int,
    ca_bundle: str | None = None,
) -> tuple[str, dict]:
    prompt = build_prompt(item)
    return call_deepseek(
        prompt=prompt,
        system=system,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        ca_bundle=ca_bundle,
    )


def progress_bar(done: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "[--------------------]"
    filled = int(width * done / total)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepSeek CLI: single prompt or batch from text-data.txt"
    )
    parser.add_argument(
        "--mode",
        choices=("single", "batch-from-text-data"),
        default="single",
        help="single: one prompt; batch-from-text-data: generate one file per #file block.",
    )
    parser.add_argument(
        "--prompt",
        required=False,
        help="User prompt text or path to a .txt file when --prompt-file is used.",
    )
    parser.add_argument(
        "--prompt-file",
        action="store_true",
        help="Interpret --prompt as a path to a UTF-8 text file.",
    )
    parser.add_argument(
        "--system",
        default="Ты пишешь связный академический текст на русском языке.",
        help="System prompt.",
    )
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--ca-bundle",
        default=os.getenv("SSL_CERT_FILE"),
        help=(
            "Path to CA bundle PEM (optional). "
            "Useful on macOS when certificate chain is not configured."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to save generated text.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Single mode: optional path to save full API JSON response.",
    )
    parser.add_argument(
        "--text-data",
        type=Path,
        default=DEFAULT_TEXT_DATA,
        help=f"Path to text-data file (default: {DEFAULT_TEXT_DATA}).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for batch mode (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Batch mode only: generate first N items (0 = all).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Batch mode only: skip if output file already exists.",
    )
    parser.add_argument(
        "--json-out-dir",
        type=Path,
        default=None,
        help="Batch mode: optional directory to save raw API responses as JSON.",
    )
    args = parser.parse_args()

    if args.mode == "single":
        if not args.prompt:
            raise RuntimeError("--prompt is required in single mode.")
        prompt = args.prompt
        if args.prompt_file:
            prompt_path = Path(prompt)
            prompt = prompt_path.read_text(encoding="utf-8")

        text, raw = call_deepseek(
            prompt=prompt,
            system=args.system,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            ca_bundle=args.ca_bundle,
        )

        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
            print(f"Saved: {args.out}")
        else:
            print(text)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Saved JSON: {args.json_out}")
        return

    items = parse_text_data(args.text_data)
    if args.limit > 0:
        items = items[: args.limit]
    if not items:
        raise RuntimeError(f"No work items found in {args.text_data}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.json_out_dir:
        args.json_out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Batch items: {len(items)}")
    started_at = time.perf_counter()
    processed = 0
    skipped = 0
    failed = 0
    durations: list[float] = []

    for idx, item in enumerate(items, start=1):
        out_path = args.out_dir / item.file_name
        if args.skip_existing and out_path.exists():
            skipped += 1
            done = processed + skipped + failed
            bar = progress_bar(done, len(items))
            print(f"{bar} [{idx}/{len(items)}] skip existing: {out_path.name}")
            continue

        done = processed + skipped + failed
        bar = progress_bar(done, len(items))
        print(f"{bar} [{idx}/{len(items)}] generating: {item.file_name} ...")
        req_started = time.perf_counter()
        try:
            text, raw = generate_one(
                item=item,
                system=args.system,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                ca_bundle=args.ca_bundle,
            )
            out_path.write_text(text.strip() + "\n", encoding="utf-8")
            print(f"Saved: {out_path}")
            if args.json_out_dir:
                json_path = args.json_out_dir / f"{Path(item.file_name).stem}.json"
                json_path.write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"Saved JSON: {json_path}")
            processed += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[{idx}/{len(items)}] failed: {item.file_name} -> {exc}")
            continue

        took = time.perf_counter() - req_started
        durations.append(took)
        done = processed + skipped + failed
        remaining = len(items) - done
        avg = sum(durations) / len(durations) if durations else 0.0
        eta_sec = int(avg * remaining)
        bar = progress_bar(done, len(items))
        print(
            f"{bar} [{idx}/{len(items)}] done in {took:.1f}s | "
            f"processed={processed}, skipped={skipped}, failed={failed}, "
            f"eta~{eta_sec}s"
        )

    total_sec = time.perf_counter() - started_at
    final_bar = progress_bar(len(items), len(items))
    print(
        f"{final_bar} Batch finished: "
        f"processed={processed}, skipped={skipped}, failed={failed}, "
        f"elapsed={total_sec:.1f}s"
    )


if __name__ == "__main__":
    main()