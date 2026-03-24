# llm-audit-service

Сервис для первичной (эвристической) оценки вероятности того, что текст был написан с использованием LLM.

## Статус проекта

Это MVP дипломного проекта. Сейчас реализован базовый пайплайн анализа текста и один рабочий endpoint: `POST /audit`.

## Что уже реализовано

- FastAPI-приложение с точкой входа в `app/main.py`
- Endpoint `POST /audit` для загрузки текста в файле
- Препроцессинг текста (приведение к lower-case, нормализация пробелов)
- Базовые метрики:
  - `lexical_diversity`
  - `burstiness`
- Простая агрегация метрик в итоговую оценку `llm_probability` (диапазон `0..1`)

## Текущие ограничения MVP

- Поддерживается только загрузка UTF-8 текста через `POST /audit`
- Роуты `auth`, `files`, `reports` пока созданы как заготовки
- Скоринг эвристический, без ML-модели и без калибровки на датасете

## Структура проекта

```text
app/
  main.py                         # точка входа FastAPI
  api/routes/
    audit.py                      # рабочий endpoint /audit
    auth.py                       # заготовка
    files.py                      # заготовка
    reports.py                    # заготовка
  services/
    analyzer.py                   # orchestration пайплайна анализа
    preprocessing/cleaner.py      # очистка текста
    metrics/
      lexical_diversity.py        # метрика лексического разнообразия
      burstiness.py               # метрика "burstiness"
    scoring/aggregator.py         # агрегация метрик в llm_probability
    ingestion/
      pdf_reader.py               # извлечение текста из PDF (пока не подключен к API)
      docx_reader.py              # извлечение текста из DOCX (пока не подключен к API)
```

## Быстрый старт

1. Создай и активируй виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Установи зависимости:

```bash
pip install fastapi uvicorn numpy pypdf python-docx python-multipart
```

3. Запусти приложение:

```bash
uvicorn app.main:app --reload
```

4. Проверь, что сервис поднялся:

- `GET /` -> `{"message": "LLM Audit Service is running"}`
- Swagger UI: `http://127.0.0.1:8000/docs`

## API: POST /audit

Принимает файл в `multipart/form-data` с полем `file`.

### Пример запроса

```bash
curl -X POST "http://127.0.0.1:8000/audit" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.txt"
```

### Пример ответа

```json
{
  "metrics": {
    "lexical_diversity": 0.73,
    "burstiness": 1.94
  },
  "llm_probability": 1.0
}
```

## Как интерпретировать результат

- `llm_probability` ближе к `0` — ниже вероятность "LLM-паттерна"
- `llm_probability` ближе к `1` — выше вероятность "LLM-паттерна"
- Текущее значение — исследовательская эвристика, а не финальный детектор

## Ближайший roadmap

- Подключить `pdf_reader` и `docx_reader` к API
- Добавить нормальную валидацию входных файлов и обработку ошибок кодировок
- Расширить набор метрик и ввести калибровку на валидационном наборе
- Добавить отчеты, хранение результатов и авторизацию
