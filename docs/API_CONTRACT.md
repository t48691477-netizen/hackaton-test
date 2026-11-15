# ПромСкан: контракты API и клиентов

FastAPI-приложение `app.main` сохраняет два HTTP-контракта: основной legacy
`/api` и совместимый формат `/front/api`. У них разные схемы запросов/ответов,
статусы и authorization. Не считать один префикс alias другого. Android
Retrofit объявляет `/api/auth/*` для входа и `/front/api/*` для оборудования,
осмотра и задач. React UI в текущем checkout остаётся demo-only: HTTP-клиент,
который вызывает эти маршруты, отсутствует.

Документ сверён с `app/routers/`, `app/schemas/`, `app/services/storage.py` и
Android Retrofit-интерфейсом. Он описывает текущую реализацию, но не утверждает,
что SQL уже применён или production-проверен. Настройка PostgreSQL описана в
[`DEPLOY.md`](DEPLOY.md).

## Общие правила

- Base URL локального сервера: `http://127.0.0.1:8000`.
- `/docs`, `/redoc`, `/openapi.json` доступны, если `TOIR_DISABLE_DOCS` не
  установлен в `true`; production proxy может скрывать документацию.
- JSON использует `snake_case`. Все координаты bbox и polygon в ответах детекции
  нормализованы относительно изображения в диапазон `0..1`, если схема явно
  не указывает иное.
- `multipart/form-data` отправлять как `FormData` или multipart parts; не
  задавать `Content-Type` вручную.
- `503` может означать ненастроенный/недоступный PostgreSQL, credentials
  storage или недоступную модель. Сам `/health` не проверяет работу БД и не
  выполняет inference.
- CORS по умолчанию отключён. Для cross-origin клиента задайте точный список
  origins через `TOIR_CORS_ORIGINS`.

## Маршруты и авторизация

| Метод и путь | Формат / назначение | Авторизация |
|---|---|---|
| `POST /api/auth/login` | вход по `access_key`, ответ с bearer token | публичный вход |
| `GET /api/auth/me` | текущий account | Bearer |
| `POST /api/auth/logout` | отзыв сессии, `204` | Bearer |
| `GET /api/users` | список активных сотрудников | Bearer, permission `users` |
| `POST /api/users` | создание сотрудника и отправка ключа, `201` | Bearer, permission `users` |
| `POST /api/users/{employee_id}/access` | ротация ключа и отправка, `200` | Bearer, permission `users` |
| `DELETE /api/users/{employee_id}` | деактивация сотрудника, `204` | Bearer, permission `users` |
| `GET /api/equipment` | legacy `EquipmentResponse[]` | Bearer, permission `scan` |
| `GET /api/equipment/{equipment_id}` | legacy `EquipmentResponse` | Bearer, permission `scan` |
| `POST /api/equipment` | JSON `EquipmentCreate`, ответ `201 EquipmentResponse` | Bearer, permission `users` |
| `POST /api/inspect` | multipart, legacy `InspectResponse` | Bearer, permission `scan` |
| `POST /api/reports` | JSON `ReportCreate`, legacy `ReportResponse` | Bearer, permission `scan` |
| `GET /api/reports` | legacy reports; query `repair_status`, `equipment_id` | Bearer, permission `dispatch` |
| `GET /api/reports/{report_id}` | legacy `ReportResponse` | Bearer, permission `dispatch` |
| `PATCH /api/reports/{report_id}/status` | JSON `ReportStatusUpdate` | Bearer, permission `dispatch` |
| `POST /api/detect` | JPEG body, компактная live-детекция | Bearer, permission `scan` |
| `GET /front/api/equipment` | совместимая карточка оборудования | сейчас без Bearer |
| `GET /front/api/equipment/{equipment_id}` | одна совместимая карточка | сейчас без Bearer |
| `POST /front/api/inspect` | multipart, быстрый результат осмотра | сейчас без Bearer |
| `GET/POST /front/api/reports` | совместимый формат задач | сейчас без Bearer |
| `GET /front/api/reports/{report_id}` | совместимая задача | сейчас без Bearer |
| `PATCH /front/api/reports/{report_id}/status` | JSON `{status, comment?}` | сейчас без Bearer |
| `POST /front/api/mail/access-key` | SMTP отправка указанного ключа | сейчас без Bearer |

У `/front/api/*` в текущей реализации нет bearer-проверок. Учитывайте это до
публикации сервиса; роли и permission основного `/api` не распространяются на
эти маршруты. Маршруты `/api/auth/confirm-email`,
`/front/api/inspect/detailed` и Android detailed-analysis endpoint отсутствуют.

## Параметры доступа `/api`

Роли: `director`, `admin`, `dispatcher`, `engineer`. Permissions:
`scan`, `dispatch`, `users`. `director`/`admin` получают все permissions,
`dispatcher` — `scan` и `dispatch`, `engineer` — `scan`. Сейчас эти проверки
применяются на защищённых `/api` маршрутах.

`POST /api/auth/login` принимает JSON:

```json
{"access_key":"PSCENG5542"}
```

Ключ нормализуется (верхний регистр, пробелы и дефисы удаляются) и проверяется
по формату из десяти символов алфавита `A-HJ-NP-Z2-9`. Ответ `200` содержит
`session_token`, `expires_at` и `account`. Токен передаётся последующими
запросами в `Authorization: Bearer <session_token>`. Сервер хранит Argon2id
key hash и SHA-256 hash session token в credentials-БД; срок сессии восемь
часов. Неверный формат даёт `422`, неверный ключ `401`, ограничение попыток
входа `429`. Logout отзывает токен и отвечает `204`.

### `/api/users`

`GET /api/users` возвращает только активных сотрудников из employees-БД,
отсортированных по `full_name`, затем по `id`. Каждый элемент содержит только
публичные поля `id`, `full_name`, `email` и `role`; `is_active`, хеши ключей и
другие credential-поля в ответ не попадают. Маршрут требует Bearer с permission
`users` (`director` и `admin`). При недоступности employees-БД возвращается
`503`.

`DELETE /api/users/{employee_id}` принимает UUID в path и также требует Bearer
с permission `users`. Сначала в отдельной транзакции employees-БД строка
сохраняется и получает `is_active = false`, затем в отдельной транзакции
credentials-БД удаляется её access-key credential. Внешние ключи удаляют вместе
с credential все зависимые `auth_sessions` и `email_verification_codes`.
Операция отвечает `204` без тела. Повторная деактивация существующего сотрудника
идемпотентна и повторяет отзыв credential. Если сотрудник не найден, ответ
`404`; некорректный UUID даёт `422`; недоступность employees или credentials
даёт `503`. Из-за раздельных баз ошибка второго шага оставляет сотрудника
неактивным и также возвращает `503`.

`POST /api/users` принимает JSON `{ "full_name", "email", "role" }`; имя
обрезается по краям, email приводится к нижнему регистру, лишние поля и
недопустимые роли отклоняются. `director` может создать `admin`, `admin` — только
`dispatcher` или `engineer`. Конфликт уникального email возвращает `409`. Сервер
генерирует ключ из 10 символов алфавита `A-HJ-NP-Z2-9`, записывает только
Argon2id PHC-хеш с отдельной 16-байтовой солью и синхронно отправляет ключ через
SMTP. Успешный ответ `201`:

```json
{
  "account": {
    "id": "00000000-0000-0000-0000-000000000001",
    "full_name": "Пётр Сидоров",
    "email": "p.sidorov@promscan.ru",
    "role": "dispatcher"
  },
  "invitation": {
    "status": "sent",
    "provider": "smtp",
    "email": "p.sidorov@promscan.ru",
    "sent_at": "2026-11-15T10:30:00Z"
  }
}
```

Plaintext ключ, `key_hash`, `key_salt`, `is_active` и поля credential не входят
в ответ. Ошибка вставки credential или отправки письма запускает компенсационное
удаление credential и employee-записи. Почтовые ошибки возвращают безопасные
`429`, `502` или `503`, без секрета и деталей БД.

`POST /api/users/{employee_id}/access` не принимает тело. Активный сотрудник
должен существовать; иначе `404`. Ключ администратора может перевыпустить только
`director`; другим ролям возвращается `403`. Credential обновляется с новым
Argon2id-хешем и явной солью; PostgreSQL trigger отзывает активные сессии при
изменении хеша или соли. Затем ключ синхронно отправляется сотруднику. При
ошибке отправки прежние хеш и соль восстанавливаются, что также отзывает уже
существовавшие сессии; API возвращает безопасную SMTP-ошибку. Успешный ответ
имеет ту же форму, что и создание, без plaintext ключа.

Backend invitation states: `not_sent`, `sent`, `failed`; `queued` не используется,
поскольку отправка синхронная. `/front/api/mail/access-key` отдельно отправляет
переданный в запросе ключ через SMTP; он не создаёт employee или credentials и
сейчас не требует Bearer.

## Оборудование

Основной `/api` возвращает legacy-модель `EquipmentResponse` из
`app/schemas/equipment.py`: `id`, `name`, `serial_number`, `location`,
`installation_date`, `component_age`, `last_maintenance_date`, `status`,
`components`, `created_at`, `updated_at`, `inspection_count`.

`POST /api/equipment` принимает `EquipmentCreate`: эти поля без серверных дат и
счётчика, `id` опционален. Реализация отвечает `201` и при создании, и при
обновлении существующего ID. Каталог читается из `promscan.webapp_equipment` в
каталожной БД. Таблица создаётся migration
`database/migrations/005_webapp_catalog.sql`; эта миграция не заполняет каталог.

Формат `/front/api/equipment` адаптирует запись к полям веб/Android DTO:
`id`, `name`, `inventory_number`, `category`, `location`, `state`,
`manufacturer`, `model`, `commissioned_at`, `service_life_years`,
`last_maintenance_at`, `next_maintenance_at`, `specs`, `nodes`, `created_at`,
`updated_at`. При отсутствии записи detail route возвращает `404`; inspect
compatibility handler может сформировать fallback-представление для
неизвестного ID.

## Детекция и осмотр

Во всех путях обнаружения используется одна модель
`weights/defects_yolo.onnx`, с переопределением пути через `UNIFIED_WEIGHTS`.
Отдельных `CORROSION_WEIGHTS`, `OIL_WEIGHTS` и `WELDING_WEIGHTS` в текущей
конфигурации нет. Модель запускается на CPU.

### `POST /api/detect`

Отправляется raw JPEG body (`Content-Type: image/jpeg`), опционально query
`conf` (`0.10..0.85`, default `0.25`), `imgsz` (`320..1024`, default `640`) и
header `X-Frame-Id`. Максимум body 5 MiB и размер стороны 4096 px. Ответ
содержит `defects`, `frame_id`, `inference_ms`, `model_loaded.unified`.
Требуется Bearer с `scan`.

### `POST /api/inspect`

Multipart поля: обязательные `file` и `equipment_id`. Handler проверяет
расширение `.jpg`, `.jpeg`, `.png`, `.webp` или `.bmp`, сохраняет исходное
изображение, вызывает единую YOLO-модель и LLM expert service, увеличивает
счётчик инспекций и возвращает `InspectResponse`:

```json
{
  "equipment_id": "pump-402",
  "equipment_name": "Насос",
  "timestamp": "2026-11-15T10:00:00Z",
  "defects_count": 1,
  "defects": [],
  "expert_opinion": {
    "criticality": "medium",
    "probable_cause": "Причина",
    "recommendations": ["Проверить узел"]
  },
  "image_url": "/static/uploads/original.jpg",
  "annotated_image_url": "/static/uploads/original_annotated.jpg"
}
```

В текущей реализации невалидное расширение даёт `400`, ошибка сохранения или
инференса может дать `500`. Если модель отсутствует или не загружается,
детектор возвращает пустой список дефектов и сохраняет аннотированное исходное
изображение. Неизвестный equipment ID не даёт `404` в этом handler: эксперт
получает fallback-контекст. Формат ответа отличается от `/front/api/inspect`.

### `POST /front/api/inspect`

Совместимый быстрый маршрут принимает multipart `file` и `equipment_id`.
Возвращает `inspection_id`, совместимую карточку `equipment`, список `defects`,
`condition_parameters`, rule-based `llm`, `summary` и `meta`. Для этого
быстрого пути `meta.vision_mode` указывает `real`, `meta.llm_mode` — `mock`;
причина и рекомендации кратко собираются из найденных категорий. Маршрут не
выполняет отдельный detailed-analysis запрос.

## Отчёты и задачи

SQL-задачи хранятся в `promscan.reports` отдельной tasks-БД. Основная схема
`database/sql/tasks/001_schema.sql` принимает статусы `open`, `in_progress`,
`closed`. Additive SQL `database/sql/tasks/002_rejected_status.sql` вводит
отдельный `rejected`: он терминален, требует назначенного исполнителя и
непустой причины в `repair_comment`; `completed_at` у rejected остаётся `NULL`.
Без 002 база не может сохранять `rejected`.

### `/api/reports` legacy-контракт

`POST /api/reports` принимает JSON `ReportCreate`:

```json
{
  "equipment_id": "pump-402",
  "repair_status": "pending",
  "dispatcher_notes": "Проверить корпус",
  "defects": [],
  "expert_opinion": {
    "criticality": "low",
    "probable_cause": "",
    "recommendations": []
  },
  "photo_url": "/static/uploads/original.jpg",
  "final_photo_url": null
}
```

Legacy status mapping: `pending → open`, `in_progress → in_progress`,
`completed → closed`, `rejected → rejected`. Создание проверяет существование
оборудования и сохраняет содержимое акта в задаче. `GET /api/reports` принимает
query `repair_status` и `equipment_id`; `PATCH /api/reports/{id}/status`
принимает JSON с полями `status` (legacy enum) и опциональным
`dispatcher_notes`. Новые переходы:

| Из статуса | В `in_progress` | В `completed` | В `rejected` |
|---|---:|---:|---:|
| `pending` | да | да | да |
| `in_progress` | нет | да | да |
| `completed` | нет | нет | нет |
| `rejected` | нет | нет | нет |

Повторная установка текущего статуса не запускает переход повторно; если в
таком запросе передан новый `dispatcher_notes`, сервис обновляет комментарий.
В legacy-контракте сервис
подставляет технический снимок исполнителя `Бригада ТОиР`, если переход из
`pending` требует исполнителя, а его нет. При переходе в `rejected` причина
берётся из `dispatcher_notes`; если поле пусто, сохраняется стандартная причина
для legacy-перехода. SQL 002 обязателен, иначе база не допустит этот статус.
Недопустимые переходы возвращают `409`, отсутствующий report — `404`. Ответ
`ReportResponse` также содержит `equipment_name`, `created_at`, `updated_at`, а
кроме того legacy fields `repair_status`, `dispatcher_notes`, `defects_count`,
`defects`, `expert_opinion`, `photo_url`, `final_photo_url`, `started_at` и
`completed_at`; это не `Report` из frontend-контракта.

### `/front/api/reports` совместимый контракт

`POST /front/api/reports` принимает multipart `equipment_id`, `inspection_id`,
`payload` (JSON-строка объекта), опциональные `status`, `comment`,
`assignee_id`, `photo`. Новая запись вставляется в `open`; начальный
`in_progress`/`closed` применяется дальнейшими SQL-переходами. Ответ включает
`id`, `equipment_id`, `inspection_id`, `status`, `comment`, `photo_url`,
`result`, `assignee`, timestamps и `repair_comment`.

`GET /front/api/reports` фильтрует по `status` из `open`, `in_progress`,
`closed`, `rejected`; `GET /front/api/reports/{id}` читает одну задачу.
`PATCH /front/api/reports/{id}/status` принимает JSON
`{"status":"in_progress"}` или `{"status":"closed","comment":"..."}`.
Новые переходы ограничены `open → in_progress → closed`; повтор текущего
статуса идемпотентен и возвращает текущую запись без перехода. Поэтому `open`
принимается только для уже открытой задачи, а `rejected` через POST или как
новый PATCH-переход установить нельзя (повтор уже установленного `rejected`
остаётся идемпотентным). Неподдерживаемый статус даёт `422`, недопустимый
переход или неназначенная задача — `409`, отсутствующий report — `404`.

Задачи хранят снимок `assignee_id` и `assignee_full_name`. `assignee_id` должен
быть UUID; сервис запрашивает активного сотрудника через employees pool, но если
запись не найдена, сейчас сохраняет UUID как `assignee_full_name`, а не
отклоняет назначение. Между физическими БД нет foreign key.

## PostgreSQL и миграции

Runtime поддерживает четыре DSN:

| Переменная | Данные |
|---|---|
| `DATABASE_URL` | каталог оборудования, включая webapp projection |
| `DATABASE_TASKS_URL` | акты/задачи |
| `DATABASE_EMPLOYEES_URL` | сотрудники |
| `DATABASE_CREDENTIALS_URL` | хеши access keys, sessions и login audit |

Рекомендуется настроить четыре отдельные PostgreSQL database, каждая со
схемой `promscan`. Каталожный пул использует `DATABASE_URL`, а при его
отсутствии может использовать `DATABASE_CATALOG_URL`. Пулы задач, сотрудников
и credentials подставляют `DATABASE_URL`, если соответствующие DSN не заданы;
при таком fallback физической изоляции нет. `/front/api/reports` при этом требует явно заданный
`DATABASE_TASKS_URL`, отличный от каталожной БД, а добавление исполнителя
требует также отдельный `DATABASE_EMPLOYEES_URL`. Переменные и setup-команды
приведены в [`DEPLOY.md`](DEPLOY.md).

Структурные SQL-файлы не исполняются автоматически приложением при старте.
`database/migrations/005_webapp_catalog.sql` добавляет таблицу совместимости
каталога в database `DATABASE_URL`. SQL создания отдельных баз и additive
миграций сотрудников, задач и credentials следует применять отдельно и в
порядке, указанном в deployment-инструкции. В этом обновлении документации не
проводились миграции на рабочей или production PostgreSQL и не заявляется
production verification.

## Клиентские ограничения и отсутствующие endpoints

- Android Retrofit объявляет вызовы `/api/auth/login`, `/api/auth/me`,
  `/api/auth/logout`, а для оборудования/осмотра/задач — `/front/api/*`.
- Android использует только быстрый `POST /front/api/inspect`; detailed
  analysis endpoint и `/front/api/inspect/detailed` отсутствуют.
- React-приложение в `src/` остаётся demo-only; HTTP-клиент не найден, поэтому
  изменение `VITE_USE_MOCK_API`/`VITE_API_BASE_URL` не подключает его к backend.
- Нет `/api/users/{id}/reissue-key`, `/api/users/{id}/invite`,
  `/api/auth/confirm-email`, WebSocket endpoint или detailed-analysis endpoint.
- `/front/api/mail/access-key` отправляет письмо сразу; это не очередь и не
  provisioning сотрудника. SMTP limit задаётся `SMTP_MAX_PER_HOUR` (default
  30) и действует в памяти процесса.
