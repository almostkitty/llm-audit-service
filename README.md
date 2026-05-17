# llm-audit-service

Веб-сервис для проверки текста: статистические метрики, сравнение с эталоном human-текстов, оценка **P(LLM)** через CatBoost, проверка скрытых Unicode и экранирований (`\$`, `\~`). Есть регистрация, история проверок и отчёты по ссылке.

## Запуск локально

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ENABLE_CATBOOST=1 uvicorn app.main:app --reload
```

База SQLite создаётся в `data/app.db`. Модель CatBoost: `models/catboost/catboost_model.cbm`.

## Docker

```bash
docker compose up --build
```

Сервис: [http://127.0.0.1:8000](http://127.0.0.1:8000). В compose по умолчанию `ENABLE_CATBOOST=1`.

## Тесты (/tests)

```bash
pip install -r requirements.txt
pytest
```
