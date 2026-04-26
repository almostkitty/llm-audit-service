"""
Универсальный экспорт метрик из SQLite в CSV.

Примеры:
  python3 tools/export_metrics_csv.py --source human
  python3 tools/export_metrics_csv.py --source llm --skip-perplexity
  python3 tools/export_metrics_csv.py --source human --out ml/dataset_human.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._metrics_export_common import (
    collect_eligible_rows,
    export_metrics_csv,
    load_rows_from_db,
)

DEFAULT_DB = PROJECT_ROOT / "data/main-domain/thesis.db"
DEFAULT_OUT_HUMAN = PROJECT_ROOT / "ml/dataset_human.csv"
DEFAULT_OUT_LLM = PROJECT_ROOT / "ml/dataset_llm.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Экспорт табличных метрик из works/llm_works в CSV",
    )
    p.add_argument(
        "--source",
        choices=("human", "llm"),
        required=True,
        help="Источник текстов: human -> works.text, llm -> llm_works.generated_text",
    )
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB, help="Путь к SQLite")
    p.add_argument("--out", type=Path, default=None, help="Выходной CSV (по умолчанию зависит от --source)")
    p.add_argument(
        "--skip-perplexity",
        action="store_true",
        help="Не считать perplexity (быстро; колонка будет NaN)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Только первые K строк после фильтра пустых (0 = все)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.db_path.is_file():
        raise SystemExit(f"База не найдена: {args.db_path}")

    if args.source == "human":
        query = "SELECT id, text FROM works ORDER BY id"
        empty_label = "id"
        id_label = "id"
        empty_error = "Нет ни одной непустой строки в works.text"
        out_path = args.out or DEFAULT_OUT_HUMAN
    else:
        query = "SELECT work_id, generated_text FROM llm_works ORDER BY work_id"
        empty_label = "work_id"
        id_label = "work_id"
        empty_error = "Нет ни одной непустой строки в llm_works.generated_text"
        out_path = args.out or DEFAULT_OUT_LLM

    rows_db = load_rows_from_db(args.db_path, query)
    eligible = collect_eligible_rows(rows_db, empty_label=empty_label, limit=args.limit)
    export_metrics_csv(
        eligible,
        out_path=out_path,
        skip_perplexity=args.skip_perplexity,
        id_label=id_label,
        empty_error_message=empty_error,
    )


if __name__ == "__main__":
    main()
