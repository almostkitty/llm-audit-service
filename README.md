# llm-audit-service


## Возможности

| Маршрут | Назначение |
|--------|------------|
| `POST /audit` | `multipart/form-data`, поле `file` — **UTF-8 текст**; ответ: `metrics`, `hidden_unicode`, `llm_probability`, `scoring` |
| `POST /extract` | Загрузка `.pdf`, `.docx`, `.rtf`, `.odt` или текстового файла; ответ `{"text": "..."}` |
| `GET /demo`, `GET /history`, `GET /info`, `GET /report/{id}` | HTML-интерфейсы |
| `GET /login`, `GET /register`, `GET /account` | Страницы входа и профиля |
| `GET /api/reports`, `GET /api/reports/{id}` | Список отчётов (`demo`, опционально `last` после вызова `/audit`) |
| `POST /api/auth/register`, `POST /api/auth/login`, … | Регистрация и JWT (см. `/docs`) |

Числовые метрики считаются по строке после `clean_text` (`app/services/preprocessing/cleaner.py`). `hidden_unicode` — по **исходной** строке до очистки. CatBoost: `ENABLE_CATBOOST=1`, файл `models/catboost/catboost_model.cbm`.

Извлечение: PDF — `pymupdf4llm`, DOCX — `python-docx`, RTF — `striprtf`, ODT — `odfpy`.


## Структура репозитория

```text
llm-audit-service/
  app/                    # FastAPI-приложение (код, шаблоны, static)
  tests/                  # pytest
  docs/                   # database.md, web_testing.md (для ВКР)
  models/catboost/        # продакшен-модель (.cbm, inference.json, …)
  data/                   # SQLite (создаётся локально, в git не коммитится)
  archive/                # офлайн: обучение, ноутбуки, colab (в git не коммитится)
  requirements.txt
  requirements-dev.txt
  Dockerfile
  docker-compose.yml
```

Внутри `app/`:

```text
app/
  main.py                 # маршруты страниц, mount /static
  api/routes/             # audit, extract, auth, reports, …
  templates/              # demo, history, report, info, login, …
  static/data/            # metric_baselines_human.json (графики), metric_baselines_reference.json (описание μ, σ)
  services/               # analyzer, metrics, scoring, ingestion, …
  db/                     # SQLModel
  core/                   # config, security (JWT)
  schemas/                # Pydantic для API
```

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Тесты: `pip install -r requirements-dev.txt && pytest`

Открой `http://127.0.0.1:8000/docs` или `http://127.0.0.1:8000/demo`.

Эталон для графиков (μ, σ, методология нормального приближения):  
`http://127.0.0.1:8000/static/data/metric_baselines_reference.json` — файл в образе Docker, скрипты не нужны.

## Docker

```bash
docker compose up --build
docker compose down
```


## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | Если не задано — SQLite в `data/app.db` от корня проекта |
| `JWT_SECRET` | Секрет подписи JWT (в продакшене задайте свой) |
| `ENABLE_CATBOOST` | `1` — считать `llm_probability` через CatBoost |
| `CATBOOST_MODEL_PATH` | Путь к `*.cbm`, иначе `models/catboost/catboost_model.cbm` |
| `ENABLE_PERPLEXITY` | `1` — добавить в `metrics` поле `perplexity` |
| `PERPLEXITY_MODEL_NAME` и др. | См. комментарии в `app/services/metrics/perplexity.py` |

## Пример: `POST /audit`

```bash
curl -s -X POST "http://127.0.0.1:8000/audit" \
  -H "accept: application/json" \
  -F "file=@./README.md"
```


```json
{
  "metrics": {
    "lexical_diversity": 0.51,
    "burstiness": 4.17,
    "average_sentence_length": 13.86,
    "text_entropy": 9.06,
    "stop_word_ratio": 0.17,
    "word_length_variation": 3.78,
    "punctuation_ratio": 0.02,
    "repetition_score": 0.10,
    "unicode": 0
  },
  "llm_probability": 0.42,
  "scoring": {
    "mode": "catboost",
    "model_path": "/path/to/model.cbm",
    "disclaimer": "Число llm_probability — не вердикт о происхождении текста: результат нужно интерпретировать вместе с метриками и источником фрагмента."
  },
  "hidden_unicode": {
    "has_signals": false,
    "counts_by_label": {},
    "counts_by_codepoint": {},
    "categories": {
      "invisible_and_special_spaces": {},
      "bidirectional_marks": {}
    },
    "latex_style_escapes": {
      "backslash_dollar": 0,
      "backslash_tilde": 0
    },
    "total_flagged_characters": 0
  }
}
```