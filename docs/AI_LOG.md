# AI LOG — журнал команды

Живой журнал подключений и решений. Новые записи — сверху.

---

### [2026-11-15] standard/gpt-6-sol (OpenCode) · PostgreSQL и employee API
- Статус: backend storage, employee provisioning/rotation/deactivation API и миграции завершены; изменения подготовлены в незакоммиченной ветке.
- Изменения: добавлены защищённые создание сотрудника с SMTP-приглашением и ротация ключа, explicit-salt Argon2id, отзыв сессий trigger-ом, компенсация ошибок, миграция invitation states `not_sent/sent/failed`, grants, тесты и обновлённые API/deploy/database инструкции.
- Проверка: `python -m pytest -q` — `106 passed, 32 skipped`; `python -m compileall -q app tests test_api.py test_auth.py test_reports.py test_detect.py run.py` и `git diff --check` — OK. Skips — PostgreSQL integration без отдельных тестовых DSN.
- Риски/заметки: live PostgreSQL зависит от отсутствующих `psycopg` и отдельных test DSN. SMTP настраивается серверными переменными. Frontend/mobile и чужие изменения не редактировались.

### [2026-11-15] gpt-6-astra (OpenCode) · employee/auth и bearer-контракт фронтенда
- Статус: в работе; продолжаю защищённое создание и ротацию ключей сотрудников, `/front/api/*` и сквозной lifecycle веб-сессии.
- Изменения: проверены обе рабочие копии, текущие PostgreSQL-сервисы, mailer, роутеры и frontend-клиенты; начинаю точечные правки поверх смешанного состояния.
- Проверка: до реализации выполнены чтение onboarding/журнала, `git status` и сверка веток; полные проверки будут после завершения.
- Риски/заметки: backend employee и credentials используют разные транзакции; plaintext ключ допустим только внутри выдачи и SMTP-доставки, не в API, логах, outbox или БД.

### [2026-11-15] gpt-6-astra (OpenCode) · создание и ротация employee access keys
- Статус: в работе; беру завершение защищённых API создания сотрудника и ротации ключа доступа, включая письмо, компенсационную очистку, миграции, тесты и документацию.
- Изменения: после обязательного onboarding дочитываю текущие auth/DB/mailer контракты и готовлю точечные изменения поверх уже существующих незакоммиченных работ.
- Проверка: проверены `docs/AGENT_ONBOARDING.md`, последние записи журнала, статус рабочей копии и текущие employee/auth файлы; полные проверки будут после реализации.
- Риски/заметки: базы сотрудников и credentials используют отдельные транзакции; plaintext access key допустим только внутри отправки письма и не должен попадать в ответ, лог или текст ошибки. PostgreSQL integration требует отдельных тестовых DSN.

### [2026-11-15] gpt-6-astra (OpenCode) · завершение PostgreSQL employee/auth и real-mode web client
- Статус: в работе; продолжаю реализацию создания и ротации ключей, защиты `/front/api/*` и сквозного login/logout для `newfront`.
- Изменения: после проверки текущих незакоммиченных изменений и обязательных onboarding-файлов дочитываю сервисы, SQL-схемы и клиентские контракты перед точечным патчем.
- Проверка: проверены `git status` обеих веток, `docs/AGENT_ONBOARDING.md` и последние записи `docs/AI_LOG.md`; полные проверки будут после реализации.
- Риски/заметки: mobile, detector и прочие UI-изменения остаются вне целевых коммитов; живые PostgreSQL-тесты зависят от отдельных тестовых DSN.

### [2026-11-15] gpt-6-astra (OpenCode) · завершение provisioning и rotation employee API
- Статус: в работе; продолжаю защищённое управление сотрудниками после реализации списка и деактивации. Изменения не закоммичены.
- Изменения: впереди создание сотрудника с отправкой access key, ротация ключа, компенсационная очистка при ошибках, миграция invitation states, grants, тесты и документация.
- Проверка: прочитаны onboarding, последние записи журнала, employee/auth/mailer сервисы и PostgreSQL-схемы. Полные проверки будут после реализации.
- Риски/заметки: нужны отдельные `DATABASE_TEST_EMPLOYEES_URL` и `DATABASE_TEST_CREDENTIALS_URL`; plaintext access key существует только во время отправки письма и не должен попадать в ответы, логи или ошибки.

### [2026-11-15] gpt-6-astra (OpenCode) · завершение employee-management API
- Статус: готово; защищённые API списка и деактивации сотрудников реализованы с раздельными PostgreSQL pools. Изменения не закоммичены.
- Изменения: добавлены `EmployeeService`, публичная схема сотрудника и `/api/users`; деактивация сохраняет строку сотрудника как `is_active = false`, затем удаляет credential с каскадом сессий и кодов подтверждения. `/api/auth/me` и вход учитывают неактивный профиль; обновлены API-контракт и deployment grants.
- Проверка: targeted unit/route/PostgreSQL tests — `16 passed, 4 skipped`; `py_compile` для изменённых auth/users/employee файлов — OK. Полный набор и live PostgreSQL зависят от окружения; тестовые DSN не заданы.
- Риски/заметки: базы employees и credentials не поддерживают общую транзакцию, поэтому ошибка удаления credential после commit сотрудника возвращает `503`, а сотрудник остаётся неактивным. Plaintext access key не попадает в API-ответы или логи.

### [2026-11-15] gpt-6-astra (OpenCode) ? employee/auth API integration
- ??????: ????????? ?????????? PostgreSQL-??????????? ???????????, bearer-?????? ? frontend API; ????????? mobile/detector-????????? ???????? ??? ?????????????.
- ?????????: ????????? onboarding, ????????? ????? ????? ? ??????? ??????? `EmployeeService`, `AuthService`, `/api/users` ? frontend API/session-??????.
- ????????: ????? ???????? ????????? `git status`, onboarding ? ????????? ?????? `docs/AI_LOG.md`; ?????? ???????? ????? ????? ?????????? ??????????.
- ?????/???????: PostgreSQL integration tests ??-???????? ??????? ????????? `DATABASE_TEST_*_URL`; push frontend ????????? ??????? ????????? `newfront` ? `origin/newfront`.


### [2026-11-15] standard/gpt-6-sol (OpenCode) · защищённое управление сотрудниками
- Статус: в работе; реализую backend API для списка, создания, ротации доступа и деактивации сотрудников. Изменения не закоммичены.
- Изменения: после проверки существующих auth/DB/mailer схем добавлю отдельный users service/router с раздельными pools сотрудников и credentials; frontend checkout не меняется.
- Проверка: перед реализацией прочитаны `docs/AGENT_ONBOARDING.md`, последние записи этого журнала, auth-контракт и PostgreSQL-схемы. Полные проверки будут после внесения кода.
- Риски/заметки: PostgreSQL интеграция требует отдельных `DATABASE_TEST_EMPLOYEES_URL` и `DATABASE_TEST_CREDENTIALS_URL`; plaintext access key не должен попадать ни в API-ответы, ни в логи.

### [2026-11-15] standard/gpt-6-sol (OpenCode) · Закрытие PostgreSQL-портирования и регрессии
- Статус: локальная реализация и регрессионные проверки завершены; реальные PostgreSQL миграции/integration и APK остаются заблокированы внешними prerequisites. Изменения не закоммичены.
- Изменения: исправлен выбор legacy/provisioned аккаунта при входе, разделены SQL rate-limit счётчики identifier/source, memory fallback чистится и ограничен по размеру; повтор `rejected` стал идемпотентным, `run.py` запускает документированный FastAPI, повреждённые строки `components_json` дают пустой список компонентов. Добавлены auth, catalog и `/front/api` regressions. Проверены аудиты catalog и API/docs; документация обновлена.
- Проверка: `python -m pytest -q` — 73 passed, 30 skipped; `python -m compileall -q app tests test_api.py test_auth.py test_reports.py test_detect.py run.py` — OK; `git diff --check` — OK. Skips — PostgreSQL integration без тестовых DSN.
- Риски/заметки: PostgreSQL-схемы/миграции и сквозной API не проверены на сервере; `/front/api/*` остаётся без Bearer-аутентификации и не должен публично выставляться без дополнительного контроля. Отдельная загрузка модели в `/front/api/inspect` и best-effort счётчик инспекций оставлены как известные риски. Нет `mobile/debug.keystore`; APK не собран. Коммит не создавался.

### [2026-11-15] standard/gpt-6-sol (OpenCode) · PostgreSQL storage/auth regression pass
- Статус: код и offline-регрессии обновлены; полный локальный набор проходит. Live PostgreSQL-интеграция остаётся непроверенной без отдельной тестовой БД/DSN.
- Изменения: login rate-limit reservation теперь несёт ID конкретной записи audit; успешный вход меняет только свою reservation. Добавлена проверка совпадения reservation с ключом/источником. Storage поддерживает чтение нормализованного `promscan.equipment` вместе с overlay `promscan.webapp_equipment`, включая паспортные `equipment_nodes`; добавлены проверки для storage/API, pool errors, rejected notes и final photo. `test_detect.py` приведён к единой модели `defects_yolo`.
- Проверка: `python -m pytest -q` — 61 passed, 30 skipped; `python -m compileall -q app tests test_api.py test_auth.py test_reports.py test_detect.py` — OK; `git diff --check` — OK. PostgreSQL skips связаны с отсутствующими `DATABASE_TEST_*_URL`.
- Риски/заметки: фактическая схема `equipment_nodes` из `database/sql/001_schema.sql` не имеет `description`, поэтому API `ComponentSchema.type` проецируется из `name`. Отдельно заказаны три read-only/изолированных агентских аудита; проверить их findings перед завершением. Коммит не создавался.

### [2026-11-15] standard/gpt-6-sol (OpenCode) · PostgreSQL API-тесты отчётов
- Статус: корневые контрактные тесты переведены с SQLite на изолированные PostgreSQL базы; тесты выполнены, но API-интеграция пропущена без тестовых DSN.
- Изменения: `test_reports.py` создаёт временные базы из `DATABASE_TEST_TASKS_URL` и `DATABASE_TEST_CATALOG_URL`, применяет схемы, защищается от совпадения тестового и production DSN, сохраняет проверки `/api/reports` и отдельно проверяет легаси-переход `pending → completed`. Добавлена эта запись в журнал.
- Проверка: `python -m pytest test_reports.py tests/test_pg_reports.py` — 3 passed, 27 skipped; `python -m compileall -q test_reports.py tests/test_pg_reports.py` — OK. Оба `DATABASE_TEST_*_URL` не заданы, поэтому PostgreSQL API-тесты не запускались.
- Риски/заметки: для полной интеграционной проверки нужны отдельные тестовые DSN с правом `CREATEDB`; production DSN использовать нельзя. Изменения не закоммичены.

### [2026-11-15] glm-5.3 (OpenCode, сабагент) · Тесты PostgreSQL-хранилища задач
- Статус: готово; тесты написаны и компилируются. Интеграционные тесты намеренно не запускались — в окружении нет `psycopg` и `DATABASE_TEST_TASKS_URL`.
- Изменения: добавлен `tests/test_pg_reports.py` — psycopg3-тесты поверх реальной схемы задач (`promscan.reports`), без правок приложения и других тестов.
  - Helpers: создание/удаление временной БД из DSN (`psycopg.conninfo`), применение `database/sql/tasks/001_schema.sql` и `002_rejected_status.sql` (002 — если файл есть), разбор множества допустимых статусов.
  - Integration (пропуск без DSN/psycopg): отчёт создаётся только в `open`; `open → in_progress` только с назначенным исполнителем; триггер проставляет `started_at`; `in_progress → closed`; `open → in_progress → rejected` с `repair_comment`; недопустимые переходы падают; список отчётов упорядочен `created_at DESC`.
  - Unit (импорт `app.services.storage` с фиктивным `DATABASE_URL`): легаси `pending → open`, `completed → closed` через `LEGACY_STATUS_TO_DB` / `DB_STATUS_TO_LEGACY`, обратное отображение всех четырёх состояний БД в `RepairStatus`.
- Проверка: `python -m compileall -q tests\test_pg_reports.py` — OK. Санити-скрипт подтвердил: прямой и обратный маппинг статусов согласованы, `001` допускает `open/in_progress/closed`, `002` добавляет `rejected`, легаси-значения в схеме не утекают. Реальный прогон pytest невозможен: нет `psycopg`, `pytest` и DSN (Python 3.14.3).
- Риски/заметки: имя временной БД — `promscan_tasks_pytest_<8 hex>`; роли нужны права CREATEDB, для PostgreSQL < 13 используется обычный `DROP DATABASE`. Тесты отказов сами скипаются на `CheckViolation`, только если `002_rejected_status.sql` отсутствует; при наличии 002 нарушение контракта считается настоящей регрессией. Для полного прогона: установить `psycopg[binary]` + `pytest` и задать `DATABASE_TEST_TASKS_URL` на тестовую БД (не боевую).

### [2026-11-15] standard/gpt-6-sol (OpenCode) · PostgreSQL и единый анализ
- Статус: в работе; серверное SQLite/JSON-хранение переводится на существующие PostgreSQL-схемы, дополнительный анализ удаляется, остаётся `weights/defects_yolo.onnx`.
- Изменения: впереди изменения FastAPI-хранилищ, конфигурации PostgreSQL, веб/Android-контрактов и очистка устаревшего второго анализа.
- Проверка: ещё не запускалась; в окружении пока не найдены `psql`, Docker, `psycopg` и `pytest`.
- Риски/заметки: веб-версия и Android — два клиента одного продукта; сохранять оба API-контракта. Схема задач ограничивает статусы `open/in_progress/closed`, а основной API использует `pending/in_progress/completed/rejected`; совместимость нужно обеспечить на границе хранилища.

### [2026-11-15] standard/gpt-6-sol (OpenCode) · PostgreSQL-паспорта оборудования
- Статус: код и инструкции подготовлены; production импорт не выполнен, потому что исходных четырёх PDF и настроенной PostgreSQL в окружении нет.
- Изменения: `backend/db.py` читает каталог и PDF из PostgreSQL; `backend/server.py` добавляет список оборудования и read-only routes документов; `backend/import_passports.py` валидирует точные имена/маппинг четырёх AMS PDF и импортирует содержимое с SHA-256; миграции `003`/`004` создают metadata/bytea и подтверждённый каталог; README, API и migrations README описывают импорт, проверку и разделение паспортных компонентов от AR nodes. Поверхностно разобраны `origin/feat/android-backend` (`bd90c69`) и `origin/backend-test` (`78b246f`), QR-поток и несовместимости контрактов записаны в README.
- Проверка: `python -m unittest backend.test_migrations_and_passports` — 6 тестов OK; `python -m compileall -q backend` — OK; `python tools/verify_demo.py` — 19 контрактных проверок OK; `git diff --check` — OK. Android сборка и миграции на реальной PostgreSQL не запускались.
- Риски/заметки: не импортировать одноимённые/посторонние PDF без проверки источника. Нужны точные PDF №1–№4 и доступ к PostgreSQL для применения миграций, импорта и сверки SHA-256. QR-ID четырём AMS не назначены; паспортные компоненты не являются AR-геометрией. До live-проверок подтвердить ротацию ранее подозревавшегося API-ключа; секреты в отчёт/Git не копировать. Подробный handoff лежит на рабочем столе, вне репозитория.

### [2026-11-14] gpt-6-astra (opencode) · PostgreSQL persistence для API
- Статус: в работе; интеграция ведётся в отдельной ветке `db-integration` от `origin/main`
- Изменения: готовится явный профиль `mock|production`, versioned PostgreSQL schema для оборудования, инспекций, дефектов, решений и актов; бинарные объекты будут вынесены в S3-compatible storage
- Проверка: после реализации будут запущены `tools/verify_demo.py`, migration checks и отдельная production persistence-проверка при наличии `DATABASE_URL`
- Риски/заметки: реальные DSN, object-storage и AI-секреты не добавляются в Git; неизвестное оборудование в production должно возвращать 404, а demo fallback останется только в mock

### [2026-11-14] Big Pickle (opencode) · проверка демо-цепочки одной командой
- Статус: готово, все 19 проверок проходят
- Задача: APK собирает другой человек, обучение YOLO ведёт другой человек —
  взял то, что не пересекается: автоматическая проверка контракта перед питчем.
- Изменения:
  - `tools/verify_demo.py` — сам поднимает `backend/server.py` на свободном
    порту и проверяет не «что-то ответило», а места, где приложение ломается
    молча: `offset_from_qr` у каждого узла, `node_id` → существующий узел,
    `polygon`/`bbox` строго 0..1, сценарий `PUMP-402` (2 красных маркера),
    пустой `VALVE-77`, формат `ACT-YYMMDD-XXXX`, `/api/chat` (400 на пустое
    сообщение), QR-страницы, CORS, незнакомое оборудование;
  - `--url` — проверить уже запущенный сервер, `--image` — настоящий кадр
    для live-режима; только стандартная библиотека Python;
  - `.github/workflows/verify-demo.yml` — та же проверка в CI на каждый push;
  - `README.md` и `docs/CHECKLIST.md` — шаг «проверка одной командой».
- Найдено и исправлено: `normalize_equipment_id` не раскодировал `%20`/`%2D`,
  то есть ID из URL-кодированной QR-ссылки не нормализовался. Добавлен `unquote`.
- Проверка: 19/19 `[OK]`, код возврата 0; `--url` на запущенном сервере — 0;
  мёртвый адрес — `[FAIL] transport`, код 1 (тест не врёт «ок»).
- Риски: Android не собирался — Kotlin не менялся, менялись только бэкенд и
  инструменты. CI не собирает APK: это отдельная задача у APK-сборщика.
- Не трогал: `datasates` (147 МБ), `ML-tests`, `backend-test`, веб-панель.

### [2026-11-13] Kimi K3 (opencode) · точка входа для внешних агентов
- Статус: создан `AGENTS.md` в корне — стандартный файл, который Codex, Cursor,
  Claude Code, Copilot и другие агенты читают автоматически.
- Честно: **реального диалога с другими моделями пока не было.** Субагенты,
  которых я запускал, — это мои же дочерние сессии внутри OpenCode, а не
  независимые участники. `docs/AI_TEAM.md` был приглашением, которое никто
  не прочитал: файла `AGENTS.md` не существовало, а именно его агенты ищут.
- Что теперь: любой агент, открывший репозиторий, получает карту проекта,
  правила, команды сборки и шаблон записи в журнал.
- Вопрос вайбкодеру: кого подключаем первым? Нужен либо второй клиент
  (Cursor / Claude Code / Codex) на этой машине, либо ключ провайдера,
  чтобы позвать модель программно.

### [2026-11-13] Kimi K3 (opencode) · палитра «Engineering Iris» + скиллы
- Статус: собрано (`BUILD SUCCESSFUL`), проверено компилятором
- Изменения:
  - `Color.kt`/`Theme.kt` переписаны: Radix Slate + Iris, жёлтый только у `Warning`;
  - `Hud.kt`: убраны уголки-визоры, карточки — скругление 14 dp + линия + полоса слева;
  - `Thumb.kt`: главная кнопка с градиентом и ореолом;
  - 60 замен `SafetyYellow` → `Indigo` в шести экранах;
  - `.opencode/skills/`: `ui-review`, `build-verify`, `backend-live-ai` + `README.md`;
  - `docs/LIBRARIES.md`: что взято, что отклонено и почему;
  - `opencode.jsonc` — явный путь к скиллам.
- Ошибка, которую поймал компилятор: при правке `Thumb.kt` старые компоненты
  остались под новыми → дубли `ThumbAction`/`ThumbSecondary`. Исправлено обрезкой
  файла до новой версии. Урок: после полной замены фрагмента проверяй число
  определений функции.
- Не проверено: внешний вид на устройстве (эмулятор снова умер по памяти).

### [2026-11-13] Kimi K3 (opencode) · live-модели, Моттэл, дизайн под одну руку
- Статус: на связи, собрано и проверено (`BUILD SUCCESSFUL`)
- Изменения:
  - бэкенд: режимы `mock`/`live` (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`),
    новый `POST /api/chat`, `/api/health` отдаёт режим и модель;
  - ассистент «Моттэл»: Canvas-персонаж в костюме и очках, диалог в BottomSheet,
    `MottelScript.kt` для офлайна;
  - UI: главные кнопки в дуге большого пальца, статусы «форма + текст»;
  - ручной ввод кода на сканере возвращён (страховка, если QR не читается).
- Проверка: `/api/health`, `/api/chat` (3 сценария + пустой запрос → 400),
  `/api/inspect`, `/api/reports`; live-режим с неверным ключом тихо падает в mock.
- Риск для следующего: эмулятор на этой машине убивается по памяти (1.3 ГБ свободно),
  финальную ревизию делаем на реальном телефоне.

### [2026-11-13] Big Pickle (opencode) · вечерняя сборка
- Статус: на связи, демо собрано, идёт финальная проверка на эмуляторе
- Сделано: приложение собирается (`BUILD SUCCESSFUL`), APK установлен,
  мок-API проверен целиком (`/equipment`, `/inspect`, `/reports`, `/qr`).
- Найдено и исправлено: бэкенд падал на печати «↳» в консоли Windows (cp1251),
  deep-link `equipment_id` не открывал AR при повторном запуске, маркеры
  перекрывали тапы по оверлею дефектов.
- Риск: эмулятор — OEM-образ Transsion, сам уводит приложение в launcher и
  гасит экран; для показа используем настоящий телефон + реальный AR.
- Вопрос вайбкодеру: есть ли Android-телефон с ARCore на стенде? Если да —
  финальную репетицию делаем на нём, эмулятор оставляем как страховку.

### [2026-11-13] Big Pickle (opencode)
- Статус: на связи, ведущий инженер сессии
- Зона: каркас проекта, AR/Compose, сборка, демо-режим
- Первое предложение: собрать «Demo mode» с локальными ответами API —
  чтобы питч не зависел от Wi-Fi и бэкенда. Это наша страховка на сцене.

### [2026-11-13] Человек-вайбкодер
- Статус: на связи
- Зона: продукт, дизайн, решения
- Первое предложение: прислать фото бумажного дизайна — перенесём в HUD-тему.
# Журнал работы ИИ

### [2026-11-15] gpt-6-astra (OpenCode) · employee management provisioning
- Статус: Взята задача завершить создание сотрудников с приглашением по email, ротацию ключей доступа, миграции, grants, тесты и документацию; реализация продолжается.
- Изменения: Запись добавлена перед началом работы; рабочее дерево и существующие изменения сохранены.
- Проверка: Прочитаны `docs/AGENT_ONBOARDING.md`, последние записи журнала и текущие employee/auth файлы.
- Риски/заметки: Live PostgreSQL проверки требуют `psycopg` и отдельных `DATABASE_TEST_EMPLOYEES_URL`/`DATABASE_TEST_CREDENTIALS_URL`; изменения должны остаться незакоммиченными.
