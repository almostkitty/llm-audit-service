# llm-audit-service

Сервис аудита использования генеративных языковых моделей для профессиональных текстов.

## Статус проекта

MVP дипломного проекта: FastAPI-сервис для анализа текста (метрики, hidden Unicode-сигналы и оценка `llm_probability`), извлечения текста из документов, базовой аутентификации и просмотра/выгрузки отчёта проверки (`demo`/`last`).

## Что уже реализовано

- FastAPI, точка входа `app/main.py`
- **`POST /audit`** — загрузка **текстового** файла (UTF-8), возврат метрик, `hidden_unicode` и `llm_probability`
- **`POST /extract`** — загрузка **PDF, DOCX, RTF, ODT или .txt**; ответ `{"text": "..."}`
- **`GET /api/reports`** — список доступных отчётов (`demo`, `last`)
- **`GET /api/reports/{report_id}`** — получение отчёта (`demo` или `last`)
- **`GET /demo`** — `templates/demo.html`: вставка текста --> запрос к `/audit`, краткая сводка по Unicode-сигналам и полный JSON
- **`GET /extract`** — `templates/extract.html` (файл --> запрос к `/extract`)
- Препроцессинг: lower-case, нормализация пробелов (`preprocessing/cleaner.py`); он применяется после подсчёта `hidden_unicode`, чтобы не съедать неразрывные и узкие пробелы
- Числовые метрики считаются по тексту после `clean_text` и попадают в `metrics` ответа **`/audit`**
- **`hidden_unicode`**: эвристика по невидимым символам, bidi-маркерам и литералам `\$` / `\~` — `metrics/hidden_unicode.py`, считается по **исходной** строке
- **`llm_probability`**: в `scoring/aggregator.py` — при **`ENABLE_CATBOOST=1`** и наличии файла модели **`extra/catboost/model.cbm`** (и `inference.json` / `metrics.json` с `feature_names`) используется **CatBoost** по тем же табличным метрикам, что при обучении; иначе — эвристика по четырём метрикам (`lexical_diversity`, `burstiness`, `average_sentence_length`, `text_entropy`)
- Извлечение текста:
  - **PDF** — `pymupdf4llm` (`pdf_reader.py`)
  - **DOCX** — `python-docx` (`docx_reader.py`)
  - **RTF** — `striprtf` (`rtf_reader.py`)
  - **ODT** — `odfpy` (`odt_reader.py`)

## Текущие ограничения MVP

- **`/audit`** принимает только содержимое как **UTF-8 текст** в поле `file`;
- Бинарный **`.doc`** (Word 97–2003) **не поддерживается**;
- Роут `reports` пока минималистичный;
- Скоринг: CatBoost (при включённом `ENABLE_CATBOOST=1` и доступной модели) либо эвристика baseline; обобщение на произвольные тексты требует расширенной калибровки

## Структура проекта

```text
app/
  main.py                         # FastAPI, GET /, /demo, /extract, /info, /login, /register, /account
  api/routes/
    audit.py                      # POST /audit
    extract.py                    # POST /extract
    auth.py                       # /api/auth/*
    reports.py                    # /api/reports/*
  templates/
    demo.html                     # UI: анализ вставленного текста
    extract.html                  # UI: извлечение из документов
  services/
    analyzer.py                   # clean_text + метрики + hidden_unicode + compute_score
    preprocessing/cleaner.py
    metrics/
      avg_lenght.py               # средняя длина предложения
      burstiness.py               # burstiness (разброс длины слов)
      hidden_unicode.py           # Unicode-сигналы (вне скоринга)
      lenght_variation.py         # разнообразие длины слов
      lexical_diversity.py        # лексическое разнообразие
      perplexity.py               # перплексия (опционально, по ENABLE_PERPLEXITY=1)
      punctuation_ratio.py        # доля знаков препинания
      repetition_score.py         # повторяемость фраз
      stop_word.py                # доля стоп-слов
      text_entropy.py             # энтропия распределения слов
    scoring/aggregator.py
    ingestion/
      pdf_reader.py               # pymupdf4llm
      docx_reader.py              # DOCX
      rtf_reader.py               # RTF
      odt_reader.py               # ODT
```

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Запуск в Docker

Запуск через Docker Compose:

```bash
docker compose up --build
```

Остановка:

```bash
docker compose down
```

Сервис будет доступен по адресу:

- `http://127.0.0.1:8000/demo`
- `http://127.0.0.1:8000/docs`


Переменные окружения для **`/audit`** (скоринг):

| Переменная | Значение |
|------------|----------|
| `ENABLE_CATBOOST` | `1` — использовать CatBoost (`CATBOOST_MODEL_PATH` или путь по умолчанию `extra/catboost/model.cbm`) |
| `CATBOOST_MODEL_PATH` | Полный путь к `*.cbm`, если модель не в каталоге по умолчанию |
| `ENABLE_PERPLEXITY` | `1` — считать перплексию в метриках |


## API: POST /audit

`multipart/form-data`, поле `file` — **текст в UTF-8** (например `.txt`).

Пример:

```bash
curl -X POST "http://127.0.0.1:8000/audit" \
  -H "accept: application/json" \
  -F "file=@sample.txt"
```

Пример ответа:

```json
{
  "metrics": {
    "lexical_diversity": 0.5169109357384442,
    "burstiness": 4.168206436059661,
    "average_sentence_length": 13.859375,
    "text_entropy": 9.060240121550303,
    "stop_word_ratio": 0.16573348264277715,
    "word_length_variation": 3.7789375941173824,
    "punctuation_ratio": 0.01972127267946358,
    "repetition_score": 0.10449623795706625,
    "unicode": 0,
    "perplexity": 19.5
  },
  "llm_probability": 0.42,
  "scoring": {
    "mode": "catboost",
    "disclaimer": "Число llm_probability — не вердикт о происхождении текста: результат нужно интерпретировать вместе с метриками и источником фрагмента."
  },
  "hidden_unicode": {
    "has_signals": false,
    "counts_by_label": {},
    "counts_by_codepoint": {},
    "categories": {
      "invisible_and_special_spaces": {},
      "bidirectional_marks": {},
      "dashes": {},
      "smart_quotes": {}
    },
    "latex_style_escapes": {
      "backslash_dollar": 0,
      "backslash_tilde": 0
    },
    "total_flagged_characters": 0
  }
}
```

## API: POST /extract

`multipart/form-data`, поле `file`:

| Расширение | Обработка |
|------------|-----------|
| **`.pdf`** | pymupdf4llm |
| **`.docx`** | python-docx |
| **`.rtf`** | пакет `striprtf` |
| **`.odt`** | пакет `odfpy` |
| **`.txt`** / без расширения | UTF-8 |

Ответ: `{"text": "извлечённый текст"}`.

## Как интерпретировать результат анализа

- **`llm_probability`** — итоговая оценка по выбранному режиму скоринга (`catboost` или эвристический baseline). Ближе к `1` — выше оценка LLM-паттерна. Значение в диапазоне `[0, 1]`.
- **`hidden_unicode`** — отдельный сигнал: наличие подозрительных символов и экранирований. Интерпретировать в связке с источником текста.

---

## Метрики в проекте
### Базовые статистические метрики
- [x] Лексическое разнообразие (lexical diversity). Файл lexical_diversity.py;
- [x] Вариативность структуры текста (burstiness). Файл burstiness.py;
- [x] Средняя длина предложений (average sentence length). Файл avg_lenght.py ;
- [x] Энтропия текста (text entropy). Файл text_entropy.py;

### LLM-ориентированные и смежные признаки
- [x] Скрытые Unicode-сигналы (`hidden_unicode`). Файл `metrics/hidden_unicode.py`; в агрегатор скоринга не входит
- [x] Перплексия (perplexity). Файл `metrics/perplexity.py`; включается флагом `ENABLE_PERPLEXITY=1` (опционально, из-за веса модели)
- [x] Коэффициент повторений (repetition score). Файл `repetition_score.py`

### Стилометрия
- [x] Доля стоп-слов (stop-word ratio). Файл stop_word.py;
- [x] Разнообразие длины слов (word lenght variation). Файл lenght_variation.py;
- [x] Доля знаков препинания (punctuation ratio). Файл punctuation_ratio.py;