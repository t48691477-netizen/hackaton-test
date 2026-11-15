# TOiR: пайплайн детекции и хранения

FastAPI-приложение `app.main` принимает изображение, запускает единую ONNX-модель
детекции дефектов и формирует ответ для одного из сохранённых контрактов API.
Это описание текущего кода, а не подтверждение установки или production-запуска.

## Запуск приложения

Из корня репозитория после установки `requirements.txt`, PostgreSQL-драйвера,
настройки DSN и применения SQL-схем:

```powershell
python -m pip install -r requirements.txt
python -m pip install "psycopg[binary,pool]"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Нужен файл `weights/defects_yolo.onnx`; альтернативный путь можно указать через
`UNIFIED_WEIGHTS`. Инференс модели выполняется на CPU. Путь `/health` проверяет
доступность процесса и сообщает признак загрузки единой модели, но не проверяет
схемы PostgreSQL и не гарантирует успешный запрос к БД или инференс.

Если включена документация FastAPI:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

Переменная `TOIR_DISABLE_DOCS=true` отключает эти маршруты.

## Пайплайн изображения

```text
Кадр
  -> единая weights/defects_yolo.onnx (Ultralytics, CPU)
  -> нормализованные bbox/polygon и категории дефектов
  -> формат ответа выбранного API-контракта
```

`/api/inspect` после детекции вызывает `TOIRExpertService`: сначала настроенную
Ollama модель, затем доступный Gemini endpoint, затем rule-based fallback.
Он возвращает собственный `InspectResponse` с `expert_opinion`.
`/front/api/inspect` использует ту же настроенную unified ONNX path и
синхронно формирует короткие `llm` cause/recommendation правилами. Это быстрый
формат совместимости; отдельного `/front/api/inspect/detailed` endpoint или
Android detailed-analysis endpoint в коде нет.

У единой модели нет раздельных файлов `corrosion_yolo26.pt`, `oil_yolo26.pt`,
`welding_yolo26.pt` в текущей настройке. В `weights/` находится
`defects_yolo.onnx`. Реальные обнаруживаемые классы зависят от этой модели;
документ не приписывает ей качество или классы без подтверждения.

## Контракты API

`/api` и `/front/api` существуют одновременно и не являются взаимозаменяемыми:

| Маршрут | Ответ и назначение |
|---|---|
| `POST /api/detect` | raw JPEG frame, компактный список детекций для live-кадра |
| `POST /api/inspect` | multipart кадр и equipment ID, `InspectResponse` + expert opinion |
| `/api/equipment`, `/api/reports` | основной legacy Pydantic-контракт |
| `POST /front/api/inspect` | быстрый совместимый inspection result с equipment, defects, `llm`, summary и meta |
| `/front/api/equipment`, `/front/api/reports` | формат карточек/задач веба и Android |

Основные `/api` маршруты детекции, оборудования, инспекций и задач требуют
Bearer с соответствующим permission; `/api/auth/login` выдаёт сессию.
Текущие `/front/api/*` не проверяют Bearer. Точный список и различия полей
описаны в [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## Формы детекции

Детекции содержат confidence `0..1`, нормализованный bbox
`[x_min, y_min, x_max, y_max]`, при наличии маски — polygon `[[x, y], ...]`.
`POST /api/detect` требует `Content-Type: image/jpeg`, имеет предел 5 MiB и
максимум 4096 пикселей по стороне. Multipart `/api/inspect` и
`/front/api/inspect` принимают `file` и `equipment_id`; основной `/api/inspect`
проверяет расширение имени, но это само по себе не доказывает формат содержимого.

В `POST /api/detect` модель недоступна — ответ `503`. `/api/inspect` сохраняет
исходное и аннотированное изображения в `static/uploads`; compat inspection
возвращает категории и детекции в своём формате. Не считать эти endpoints
асинхронной очередью или WebSocket stream.

## PostgreSQL

Приложение подключается по PostgreSQL DSN:

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | каталог оборудования и webapp catalog projection |
| `DATABASE_TASKS_URL` | акты/задачи |
| `DATABASE_EMPLOYEES_URL` | employee directory |
| `DATABASE_CREDENTIALS_URL` | access-key hashes, session hashes и login audit |

Схемы в каждой базе называются `promscan`. Рекомендуемый layout использует
четыре отдельные физические базы; если DSN `DATABASE_TASKS_URL`,
`DATABASE_EMPLOYEES_URL` или `DATABASE_CREDENTIALS_URL` не заданы, код
совместимости может использовать `DATABASE_URL`, то есть изоляции в этом случае
нет. PostgreSQL не выполняет foreign keys между базами: задача хранит snapshot
исполнителя.

Путь SQL для каталога `promscan.webapp_equipment` —
`database/migrations/005_webapp_catalog.sql`; задачи —
`database/sql/tasks/001_schema.sql` плюс additive
`database/sql/tasks/002_rejected_status.sql`; сотрудники —
`database/sql/employees/001_schema.sql`; credentials —
`database/sql/credentials/001_schema.sql`, `002_key_salt_and_login_audit.sql`,
`003_enforce_key_salt.sql`. Последний credentials SQL допускается только после
заполнения всех salts. Приложение не запускает эти SQL автоматически.

### Статусы задач

SQL `tasks/001_schema.sql` задаёт `open`, `in_progress`, `closed` и триггер
жизненного цикла `open → in_progress → closed`. Основной `/api/reports` сохраняет
legacy значения `pending`, `in_progress`, `completed`, `rejected`, отображая
`pending → open`, `completed → closed`. `tasks/002_rejected_status.sql`
добавляет отдельное сохраняемое `rejected`, требует assigned snapshot и
непустой `repair_comment`, запрещает переход из `closed` и делает `rejected`
терминальным. Эта миграция является SQL-артефактом; её наличие в checkout не
доказывает применение к какой-либо базе.

`/front/api/reports` работает с `status` `open`, `in_progress`, `closed` и
`rejected` в GET; его POST и PATCH сейчас допускают только обычный open/work/
closed поток. Статус `rejected` для legacy API требует применения SQL 002.

## Данные, которые не загружаются

Файл `database/sql/004_seed_measurement_catalog.sql` регистрирует две
синтетические demo-партии вибрации и температуры как `rejected`. Причины
отклонения записаны в манифестах; строки demo-измерений и диагнозы в таблицы
не загружаются. Изменение документации или наличие seed SQL не означает, что
эти файлы или другие миграции уже применялись.

## Статус проверки

В этой задаче проверяется согласованность документации с текущими маршрутами,
DSN-настройкой и SQL-файлами. Успешное применение схем, миграция данных,
проверка целевого PostgreSQL и production smoke test здесь не утверждаются.
