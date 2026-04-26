"""
Сбор датасета ВКР из каталога с оригинальными файлами.

По умолчанию читает `data/main-domain/`, пишет SQLite и очищенные txt.

Пример:
  python3 tools/build_thesis_dataset.py
  python3 tools/build_thesis_dataset.py --input /path/to/main-domain \\
    --db data/thesis_corpus.sqlite --txt-out data/thesis_clean_txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thesis_dataset import run_pipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Пайплайн: файлы → SQLite + txt.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/main-domain"),
        help="Каталог с файлами <id>_<название>.{pdf,docx,...}",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/thesis_corpus.sqlite"),
        help="Путь к SQLite",
    )
    parser.add_argument(
        "--txt-out",
        type=Path,
        default=Path("data/thesis_clean_txt"),
        help="Каталог для <id>.txt (очищенное тело)",
    )
    args = parser.parse_args()

    if not args.input.is_dir():
        raise SystemExit(f"Нет каталога: {args.input}")

    run_pipeline(args.input, args.db, args.txt_out)
    print(f"Готово. БД: {args.db}, txt: {args.txt_out}")


if __name__ == "__main__":
    main()
