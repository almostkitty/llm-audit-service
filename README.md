# llm-audit-service

Diploma project

Сервис для оценки вероятности того, что текст был написан с использованием LLM.

## Статус проекта

MVP дипломного проекта: анализ текста по эвристическим метрикам, простая страница для проверки API и отдельная страница для теста извлечения текста из документов.

## Что уже реализовано

- FastAPI, точка входа `app/main.py`
- **`POST /audit`** — загрузка **текстового** файла (UTF-8), возврат метрик и `llm_probability`
- **`POST /extract`** — загрузка **PDF, DOCX или .txt**; ответ `{"text": "..."}` (плоский текст для проверки пайплайна извлечения)
- **`GET /demo`** — статическая страница `templates/demo.html` (текст → запрос к `/audit`)
- **`GET /extract`** — статическая страница `templates/extract.html` (файл → запрос к `/extract`)
- Препроцессинг: lower-case, нормализация пробелов (`preprocessing/cleaner.py`)
- Метрики (см. раздел внизу); все перечисленные ниже считаются и попадают в JSON ответа **`/audit`**
- **`llm_probability`**: эвристика в `scoring/aggregator.py` (сейчас в скор входят только часть метрик — см. ниже)
- Извлечение текста:
  - **PDF** — [pymupdf4llm](https://pypi.org/project/pymupdf4llm/) (`to_text`, опционально `to_json` в `pdf_reader.py`)
  - **DOCX** — `python-docx` (`docx_reader.py`, при необходимости JSON-обёртка `extract_docx_as_json`)

## Текущие ограничения MVP

- **`/audit`** принимает только содержимое как **UTF-8 текст** в поле `file` (не PDF/DOCX напрямую). Для PDF/DOCX сначала извлеки текст через **`/extract`** или локально через `ingestion/*`
- Роуты `auth`, `files`, `reports` — заготовки
- Скоринг без ML и без калибровки на датасете; веса в `aggregator.py` — baseline

## Зависимости

Основное задаётся в `requirements.txt`: `fastapi`, `uvicorn`, `numpy`, `python-docx`, `python-multipart`, `pymupdf4llm` (подтягивает PyMuPDF).

## Структура проекта

```text
app/
  main.py                         # FastAPI, GET /, /demo, /extract
  api/routes/
    audit.py                      # POST /audit
    extract.py                    # POST /extract
    auth.py, files.py, reports.py # заготовки
  templates/
    demo.html                     # UI: анализ вставленного текста
    extract.html                  # UI: извлечение из PDF/DOCX/TXT
  services/
    analyzer.py                   # сбор метрик + compute_score
    preprocessing/cleaner.py
    metrics/                      # отдельный файл на метрику
    scoring/aggregator.py
    ingestion/
      pdf_reader.py               # pymupdf4llm: to_text / extract_pdf_as_json
      docx_reader.py              # plain text + extract_docx_as_json
```

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Проверка:

- `GET /` — `{"message": "LLM Audit Service is running"}`
- Swagger: `http://127.0.0.1:8000/docs`
- UI анализа: `http://127.0.0.1:8000/demo`
- UI извлечения: `http://127.0.0.1:8000/extract`

## API: POST /audit

`multipart/form-data`, поле `file` — **текст в UTF-8** (например `.txt`).

Пример:

```bash
curl -X POST "http://127.0.0.1:8000/audit" \
  -H "accept: application/json" \
  -F "file=@sample.txt"
```

Пример ответа (поле `metrics` может отличаться численно):

```json
{
  "metrics": {
    "lexical_diversity": 0.7665198237885462,
    "burstiness": 3.5247411522243968,
    "average_sentence_length": 5.675,
    "text_entropy": 7.25812197417637,
    "stop_word_ratio": 0.1963470319634703,
    "word_length_variation": 3.5739396701033814,
    "punctuation_ratio": 0.03647586980920314
  },
  "llm_probability": 1
}
```

**Про `llm_probability`:** в `aggregator.py` сейчас усредняются с весами `0.25` только `lexical_diversity`, `burstiness`, `average_sentence_length`, `text_entropy`. Остальные метрики в ответе есть, но в скор пока не входят — их можно добавить после калибровки или обучения.

## API: POST /extract

`multipart/form-data`, поле `file` — файл с расширением **`.pdf`**, **`.docx`** или текстовый **`.txt`** (или без расширения — обработка как UTF-8 текста).

Ответ: `{"text": "извлечённый текст"}`.

## Как интерпретировать результат анализа

- `llm_probability` ближе к `0` — ниже эвристическая «оценка LLM-паттерна»
- ближе к `1` — выше
- это не судебно значимый детектор, а исследовательский baseline

## Ближайший roadmap

- Подключить **`/audit`** к загрузке PDF/DOCX (один шаг: извлечь + `analyze_text`) или единый endpoint
- Нормализация метрик и осмысленные веса / логистическая регрессия по датасету
- Метрики `perplexity`, `repetition_score`
- Отчёты, хранение результатов, авторизация

## Метрики в проекте
### Базовые статистические метрики
- [x] Лексическое разнообразие (lexical diversity). Файл lexical_diversity.py;
- [x] Вариативность структуры текста (burstiness). Файл burstiness.py;
- [x] Средняя длина предложений (average sentence length). Файл avg_lenght.py ;
- [x] Энтропия текста (text entropy). Файл text_entropy.py;

### LLM-ориентированные метрики
- [ ] Перплексия (perplexity). Файл perplexity.py;
- [ ] Коэффициент повторений (repetition score). Файл repetition_score.py;

### Стилометрия
- [x] Доля стоп-слов (stop-word ratio). Файл stop_word.py;
- [x] Разнообразие длины слов (word lenght variation). Файл lenght_variation.py;
- [x] Доля знаков препинания (punctuation ratio). Файл punctuation_ratio.py;