# Диаграммы (PlantUML)

---

## Рис. ML-пайплайн: подготовка данных и обучение CatBoost

```plantuml
@startuml ml_pipeline_offline
skinparam shadowing false
skinparam defaultFontName Arial
skinparam roundcorner 8

title Подготовка корпуса и обучение классификатора (оффлайн)

rectangle "Исходные документы" as docs {
  card "Human\n(pdf/docx/…)" as Hdoc
  card "Промпт + API\n(LLM-тексты)" as Lgen
}

rectangle "Хранение и метрики" as store {
  database "SQLite\n(works, llm_works)" as db
  file "CSV метрик\n(dataset_human,\ndataset_llm)" as csv
}

rectangle "Датасет для ML" as mlset {
  file "dataset_train.csv\n(label 0/1)" as train
}

rectangle "Обучение" as learn {
  artifact "CatBoost\ntrain" as tr
  file "model.cbm\nmetrics.json\ninference.json" as model
}

Hdoc --> db : build_thesis_dataset
Lgen --> db : llm-generation
db --> csv : export_metrics_csv
csv --> train : build_classification_dataset
train --> tr
tr --> model

@enduml
```

---

## Рис. Пайплайн инференса в веб-сервисе (`/audit`)

```plantuml
@startuml ml_pipeline_online
skinparam shadowing false
skinparam defaultFontName Arial
skinparam roundcorner 8

title Анализ текста пользователя (онлайн)

actor "Клиент" as user
component "POST /audit" as api
rectangle "analyzer:\nметрики + hidden_unicode" as an

rectangle "Скоринг" as sc {
  artifact "CatBoost\n(model.cbm)" as cb
  artifact "Эвристика\n(baseline)" as fb
}

file "JSON:\nmetrics, llm_probability,\nscoring, hidden_unicode" as out

user --> api : multipart\n(UTF-8 текст)
api --> an
an --> sc
sc --> cb : CatBoost включён,\nмодель найдена
note right of cb
  Порядок признаков
  из inference.json
end note
sc --> fb : иначе
cb --> out
fb --> out
an ..> out : metrics,\nhidden_unicode

@enduml
```

---

## Рис. Общая схема компонентов сервиса (кратко)

```plantuml
@startuml system_overview
skinparam shadowing false
skinparam defaultFontName Arial

title Прототип сервиса аудита текста (обзор)

actor Пользователь as U

package "Клиент" {
  [Браузер\n(demo, extract, …)] as web
}

package "Сервер (FastAPI)" {
  [Маршруты\n/audit /extract\n/api/*] as routes
  [Анализ текста\nanalyzer] as an
  [Извлечение\nиз документов] as ex
  [Auth JWT] as auth
  [Reports] as rep
  database "SQLite\nпользователи" as sqldb
}

package "ML-артефакты" {
  file "model.cbm" as mdl
}

U --> web
web --> routes
routes --> an
routes --> ex
routes --> auth
routes --> rep
auth --> sqldb
an --> mdl

@enduml
```

---

## Рис. Схема базы данных веб-сервиса (SQLite)

Используется файл по умолчанию `data/app.db` (или `DATABASE_URL`). Таблицы задаются моделями SQLModel в `app/db/models.py`. Таблицы корпуса ВКР (`works`, `llm_works`) относятся к **оффлайн-пайплайну** и в приложение FastAPI не входят.

```plantuml
@startuml web_service_db
skinparam shadowing false
skinparam defaultFontName Arial
skinparam roundcorner 6
skinparam linetype ortho

title Схема БД веб-сервиса (SQLite)

hide circle

entity "users" as users {
  * id : INTEGER <<PK>>
  --
  * email : VARCHAR(320) <<UK>>
  * password_hash : VARCHAR(255)
  * is_active : BOOLEAN
  * role : VARCHAR(32)
  --
  * created_at : DATETIME
}

entity "app_settings" as app_settings {
  * id : INTEGER <<PK>>
  --
  * key : VARCHAR(128) <<UK>>
  * value : TEXT
  --
  * updated_at : DATETIME
}

note bottom of users
  Учётные записи для /api/auth/*
  (JWT выдаётся по email/паролю).
end note

note bottom of app_settings
  Ключ–значение для глобальных настроек;
  между таблицами связей FK нет.
end note

@enduml
```
