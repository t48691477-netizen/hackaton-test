# ПромСкан

Система промышленного зрения для **КСТ Энерго**. Камера снимает узел оборудования, модель ищет на кадре дефекты, система выдаёт заключение и создаёт заявку на ремонт. Заявку ведёт диспетчер, выполняет рабочий.

## Из чего состоит

| Часть | Стек | Где |
|---|---|---|
| Веб-панель | React 19, TypeScript, Vite, Tailwind | `src/` (актуальная версия в ветке `newfront`) |
| Бэкенд | FastAPI, PostgreSQL, Ultralytics YOLO, LLM с rule-based fallback | `app/` |
| Мобильное приложение | Kotlin, Jetpack Compose, CameraX, ML Kit | `mobile/` |
| Старый Android-клиент «AR-Инспектор» | Kotlin, Compose | `app/src/main/java/` (устаревший, не развивается) |

```
Камера (веб или телефон) ─ кадр ─► Бэкенд ─► единая YOLO-модель ─► дефекты на кадре
                                       │
                                       ▼
                    критичность, причина, рекомендации (LLM или шаблоны)
                                       │
                       «Создать заявку» ─► Диспетчер ─► Рабочий
```

## Быстрый старт

### Бэкенд

Нужны Python 3.11+, PostgreSQL и файл `weights/defects_yolo.onnx`. Инференс
этой единой ONNX-модели выполняется на CPU; пути к отдельным моделям для
коррозии, масла и сварки больше не используются.

```bash
pip install -r requirements.txt
pip install "psycopg[binary,pool]"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Перед запуском настройте четыре PostgreSQL DSN и примените SQL-схемы из
[`docs/DEPLOY.md`](docs/DEPLOY.md). Без PostgreSQL endpoints каталога и задач
возвращают `503`. Проверка процесса: `GET http://127.0.0.1:8000/health`;
успешный health-check не подтверждает применение схем или работу API с БД.
Подробности пайплайна: [`TOIR_PIPELINE.md`](TOIR_PIPELINE.md).

Настройки в переменных окружения (секреты не коммитить):

| Переменная | Назначение |
|---|---|
| `TOIR_ACCESS_KEY_HASH` | хеш ключа доступа |
| `LOGIN_FP_SECRET` | обязательный серверный секрет HMAC-отпечатков для входа по PostgreSQL |
| `TOIR_CORS_ORIGINS` | разрешённые источники для веб-панели |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | отправка писем с ключами |
| `OLLAMA_MODEL`, `OLLAMA_URL` | локальная LLM для экспертного заключения; URL по умолчанию `http://127.0.0.1:11434` |
| `GEMINI_API_KEY` | Gemini после Ollama; при отсутствии/ошибке используется rule-based fallback |
| `LLM_MODEL` | модель Gemini; по умолчанию `gemini-2.5-flash` |
| `OPENAI_API_KEY` | текущий экспертный сервис не использует этот ключ |
| `UNIFIED_WEIGHTS` | путь к единой модели; по умолчанию используется `weights/defects_yolo.onnx` |
| `DATABASE_URL` | PostgreSQL DSN каталога оборудования; при отсутствии пул каталога может использовать `DATABASE_CATALOG_URL` |
| `DATABASE_TASKS_URL` | PostgreSQL DSN актов и задач; пул может использовать `DATABASE_URL`, но `/front/api/reports` требует отдельную БД |
| `DATABASE_EMPLOYEES_URL` | PostgreSQL DSN сотрудников; пул может использовать `DATABASE_URL`, но назначение сотрудника в `/front/api/reports` требует отдельную БД |
| `DATABASE_CREDENTIALS_URL` | PostgreSQL DSN ключей и сессий; при отсутствии берётся `DATABASE_URL` |

### Веб-панель

```bash
npm install
npm run dev
```

Vite доступен локально на `http://127.0.0.1:5173`. В текущем checkout веб-панель не подключена к HTTP API: сценарии остаются демонстрационными, а `VITE_USE_MOCK_API` и `VITE_API_BASE_URL` не переключают запросы. В конфигурации нет proxy или HTTPS; для камеры на другом устройстве потребуется отдельно настроенный HTTPS-доступ.

### Мобильное приложение

См. [`mobile/README.md`](mobile/README.md). Нужны JDK 21 и Android SDK, `debug.keystore` создаётся один раз по инструкции. Адрес сервера вводится в настройках приложения: `http://<IP компьютера>:8000/`.

## API

| Префикс | Назначение | Авторизация |
|---|---|---|
| `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` | вход по ключу и bearer-сессия | login открыт; остальные требуют Bearer |
| `/api/users` | список, создание, ротация ключа и деактивация сотрудников | Bearer с permission `users` |
| `/api/detect` | live-детекция одного JPEG-кадра | Bearer |
| `/api/equipment`, `/api/inspect`, `/api/reports` | основной TOiR API, собственные схемы и статусы | Bearer с permission по маршруту |
| `/front/api/equipment`, `/front/api/inspect`, `/front/api/reports` | совместимый формат оборудования, быстрого осмотра и задач для Android; React-панель остаётся demo-only | маршруты сейчас не требуют Bearer |
| `/front/api/mail/access-key` | отправка письма с ключом доступа | маршрут сейчас не требует Bearer |

Маршруты `/api` и `/front/api` сохранены как отдельные контракты, а не взаимозаменяемые aliases. В `/front/api/inspect` используется синхронный быстрый анализ; `/front/api/inspect/detailed` и Android detailed-analysis endpoint отсутствуют. Подробнее: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Координаты детекций нормализованы `0..1` там, где это предусмотрено конкретной схемой.

## Роли

| Роль | Доступ |
|---|---|
| `director` | сканер, панель, сотрудники, ключи администраторов |
| `admin` | сканер, панель, сотрудники |
| `dispatcher` | сканер, панель дефектов |
| `engineer` | сканер, своя задача |

## Ограничения

- Фактические классы детекции зависят от содержимого `weights/defects_yolo.onnx`; они не перечисляются без проверки файла весов.
- Маршруты `/front/api/*` сейчас не проверяют bearer-сессию. Не выставляйте их публично без отдельного ограничения доступа.
- Единая модель `weights/defects_yolo.onnx` выполняет детекцию; отдельного маршрута подробного анализа нет. `/api/inspect` вызывает экспертный сервис, а `/front/api/inspect` формирует быстрый rule-based результат.
- Создание сотрудника и ротация ключа требуют настроенного server-side SMTP; ключ показывается только в письме и никогда не возвращается API.

Безопасность: [`SECURITY.md`](SECURITY.md).

## PostgreSQL

FastAPI-приложение использует четыре PostgreSQL DSN: каталог (`DATABASE_URL`),
задачи (`DATABASE_TASKS_URL`), сотрудники (`DATABASE_EMPLOYEES_URL`) и
учётные данные (`DATABASE_CREDENTIALS_URL`). Схемы называются `promscan`, но
каждый DSN может указывать на отдельную физическую базу. Пулы могут использовать
`DATABASE_URL` как fallback, однако compatibility `/front/api/reports` требует
отдельный `DATABASE_TASKS_URL`, а назначение исполнителя в этом контракте — ещё
и отдельный `DATABASE_EMPLOYEES_URL`. SQL-наборы, runtime-роли и команды
первоначальной настройки описаны в [`docs/DEPLOY.md`](docs/DEPLOY.md).

Изменения кода и документации не являются доказательством того, что SQL был
применён: в рамках этой документации запуск PostgreSQL-миграций и production
проверка не подтверждались.
