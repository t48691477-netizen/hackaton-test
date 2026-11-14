# AR-Инспектор · Кибер 102

Мобильный ассистент обходчика: **QR на оборудовании → AR-схема узлов → ИИ-поиск
дефектов → акт в PDF**.

Android · Kotlin · Jetpack Compose · ML Kit · SceneView/ARCore · Retrofit

---

## Что происходит по шагам

| Шаг | Экран | Действие | Технология |
|-----|-------|----------|------------|
| 1 | Сканер | Камера читает QR вида `PUMP-402` → `GET /api/equipment/PUMP-402` | CameraX + ML Kit Barcode Scanning + Retrofit |
| 2 | AR-сцена | QR становится якорем `(0,0,0)`, по `components[].offset_from_qr` расставляются 3D-маркеры узлов | SceneView + ARCore (Filament) |
| 3 | ИИ-сканирование | Кадр камеры → `POST /api/inspect` → полигоны ржавчины и рамки трещин поверх видео | Canvas overlay |
| 4 | Маркеры | `status = high` или дефект в радиусе узла → маркер узла краснеет | 3D MaterialInstance |
| 5 | BottomSheet | Узел, дефект, инженерный разбор LLM, статус решения | Compose Material3 |
| 6 | Акт | `POST /api/reports` → номер акта → PDF → «Поделиться» | PdfDocument + FileProvider |

## Быстрый старт

```bash
# 1. Мок-бэкенд (Python 3, без зависимостей)
python backend/server.py
# http://localhost:8080/qr/PUMP-402 — страница с QR для демонстрации

# 2. Сборка
./gradlew :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk

# 3. Установка
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

В Android Studio: открыть папку `repo`, `Run ▶`. JDK 17 обязателен
(`File → Settings → Build → Gradle → Gradle JDK → 17`).

### Проверка одной командой

Перед показом — убедиться, что бэкенд отвечает по контракту `docs/API.md`:

```bash
python tools/verify_demo.py
```

Скрипт сам поднимает `backend/server.py` на свободном порту и проверяет
19 пунктов: `offset_from_qr` у каждого узла, `node_id` → существующий узел,
нормализованные `polygon`/`bbox`, сценарий `PUMP-402` (должны быть красные
маркеры), пустой сценарий `VALVE-77`, формат `ACT-YYMMDD-XXXX`, `/api/chat`,
QR-страницы и CORS. Код возврата `1` — демо не готово. Зависимостей нет.

Проверить уже запущенный сервер: `python tools/verify_demo.py --url http://localhost:8080`.
В live-режиме нужен настоящий кадр: `--image photo.jpg`.

### Адрес API

| Где запущено приложение | Base URL |
|---|---|
| Эмулятор | `http://10.0.2.2:8080/` (по умолчанию) |
| Телефон в той же Wi-Fi | `http://<IP-ноутбука>:8080/` |

Меняется в приложении: **Сканер → «Сеть и режим»**. Там же переключатель
**Демо-режим** — `ON` по умолчанию: приложение отвечает локально и работает без
сети и без бэкенда. В том же окне — состояние сервера (`MOCK` / `LIVE AI`).

## Реальные модели (live-режим)

Приложение никогда не ходит к AI-провайдеру напрямую: только `backend/server.py`.
Ключ живёт на сервере, в APK его нет.

```powershell
$env:LLM_BASE_URL = "https://api.openai.com/v1"   # любой OpenAI-совместимый
$env:LLM_API_KEY  = "sk-..."
$env:LLM_MODEL    = "gpt-4o-mini"
python backend/server.py
```

Без этих переменных сервер работает в `mock`-режиме — и это не ошибка, а страховка.
Подробно: [`docs/LIVE_AI.md`](docs/LIVE_AI.md).

### Production persistence

Backend использует явный `APP_PROFILE=mock|production`. Значение по умолчанию
`mock` сохраняет полностью автономное демо. Production не переключается на mock
при ошибке конфигурации, PostgreSQL, object storage или live AI.

```powershell
python -m pip install -r backend/requirements.txt
$env:APP_PROFILE = "production"
$env:DATABASE_URL = "postgresql://<role>:<password>@<host>:5432/promscan"
$env:OBJECT_STORAGE_ENDPOINT = "https://s3.example.internal"
$env:OBJECT_STORAGE_BUCKET = "promscan-private"
$env:OBJECT_STORAGE_ACCESS_KEY = "<access-key>"
$env:OBJECT_STORAGE_SECRET_KEY = "<secret-key>"
$env:LLM_BASE_URL = "https://api.example/v1"
$env:LLM_API_KEY = "<server-only-key>"
$env:LLM_MODEL = "<vision-model>"
python backend/migrate.py
python backend/server.py
```

Миграции запускаются отдельной командой выше либо при старте приложения с
`DB_AUTO_MIGRATE=true`. Используйте отдельную миграционную роль, если роль API
не должна иметь DDL-доступ. Health production отвечает `503`, пока обязательные
PostgreSQL, S3-compatible storage или live AI не настроены/не готовы.
Неизвестное оборудование возвращает `404`. Фото инспекций и PDF-акты хранятся
во внешнем S3-compatible object storage. PDF-паспорта оборудования хранятся в
`promscan.equipment_documents.content` (`bytea`) вместе с SHA-256, размером и
временем импорта; runtime не загружает их с Яндекс.Диска и не использует
`source_path` как URL. Подробности и фактический статус переноса:
[`database/migrations/README.md`](database/migrations/README.md).

### Импорт PDF-паспортов AMS

Миграция `004_verified_pump_passports.sql` добавляет четыре записи оборудования
с серийными номерами `21031004-1` … `21031004-4`, подтверждённые характеристики,
компоненты паспорта и метаданные ожидаемых файлов. Это **не означает, что PDF уже
загружены**: исходные файлы в текущем checkout/Downloads не найдены. Пустой
`content` означает «ожидает импорта»; произвольные PDF не использовать.

Положите ровно эти четыре исходных файла в отдельную локальную папку:

```text
1) Насос №1 ПС.pdf
1) Насос №2 ПС.pdf
1) Насос №3 ПС.pdf
1) Насос №4 ПС.pdf
```

Затем на сервере с настроенным `DATABASE_URL`, установленными зависимостями и
применёнными миграциями выполните:

```powershell
$env:APP_PROFILE = "production"
python -m pip install -r backend/requirements.txt
python backend/migrate.py
python backend/import_passports.py "D:\\incoming\\pump-passports"
```

Импорт принимает только указанные имена, ровно четыре PDF, проверяет заголовок
`%PDF-`, маркер `%%EOF`, ограничение `MAX_EQUIPMENT_PDF_BYTES` (по умолчанию
25 MiB) и рассчитывает SHA-256. Все четыре строки оборудования/документов и
серийные номера сверяются до одной транзакционной записи; повторный импорт
идемпотентен. Если содержимое уже загруженного документа отличается, импорт
остановится. `--replace` разрешает замену только после того, как оператор
проверил источник:

```powershell
python backend/import_passports.py "D:\\incoming\\pump-passports" --replace
```

Проверка в PostgreSQL:

```sql
SELECT e.serial_number, d.file_name, d.byte_size,
       encode(d.sha256, 'hex') AS sha256, d.imported_at,
       d.content IS NOT NULL AS content_available
FROM promscan.equipment_documents AS d
JOIN promscan.equipment AS e ON e.id = d.equipment_id
WHERE d.document_type = 'passport'
ORDER BY e.serial_number;
```

До фактического импорта ожидаются 4 метаданные и 0 доступных документов;
после успешного импорта — 4 доступных документа, ненулевые размеры, SHA-256
длиной 64 hex-символа и `imported_at`. Список выдаёт
`GET /api/equipment/{id}/documents`, бинарный PDF —
`GET /api/equipment/{id}/documents/{document_id}`. Оба production endpoint читают
только PostgreSQL; если байтов нет, скачивание вернёт `404`.

### QR и параллельный backend в GitHub

На момент проверки опубликованная ветка `origin/feat/android-backend` указывает
на `bd90c69` (`feat(mobile): pick equipment from server list in manual dialog`,
15.11.2026); `origin/backend-test` (`78b246f`) — отдельная TOiR/YOLO-реализация.
Локальные ветки `backend`/`backend-feature` не имеют опубликованных удалённых
веток. Обе опубликованные реализации существуют отдельно от этого PostgreSQL
production профиля и не были слиты в него.

- QR сканирует Android через ML Kit. `QrParser.extractEquipmentId()` берёт
  последний сегмент URL до `?`, либо ищет текстовый ID. Серверный QR resolver,
  QR registry и выпуск производственных кодов в этой backend-ветке не добавлены.
- Ручной выбор в `feat/android-backend` загружает список из
  `GET /front/api/equipment`; недавний коммит добавил список в диалог. Обычный
  скан вызывает `GET /front/api/equipment/{id}`. Это не текущий контракт
  `GET /api/equipment/{id}` и не его `{components: offset_from_qr, radius}` DTO.
- Ветка построена вокруг другого FastAPI/SQLite хранилища, входа по access key,
  web-панели и своего multipart API инспекций/актов. Не подключайте её DTO или
  SQLite seed непосредственно к `promscan` без миграции и явного mapping.
- `front/api/inspect` на неизвестный ID может подставить `_eq_fallback`, а
  `inspect` — продолжить без найденного оборудования. В `APP_PROFILE=production`
  текущего backend неизвестный ID должен завершаться `404`; mock-каталог остаётся
  доступен только в mock-профиле.
- Парсер мобильной ветки возвращает путь после последнего `/` буквально. Это
  работает для `https://host/eq/pump-402?tab=info`, но не покрывает произвольные
  URL-схемы/форматы payload и percent-encoding во всех случаях. QR должен
  содержать утверждённый `qr_id` или alias из реестра, а не display name.
- Паспортные AMS имеют серийные номера `21031004-1` … `21031004-4`, но
  подтверждённых QR-ID для них нет. Их не следует добавлять к печатным QR или
  назначать им существующие demo ID `PUMP-402`/`PUMP-118`/`VALVE-77`.

Перед стыковкой выбрать один API как источник истины, согласовать auth для
Android, mapping QR→equipment и форму AR-компонентов. Паспортные `equipment_components`
содержат названия/характеристики, не координаты; в AR-ответ попадают только
`equipment_nodes` с явно заданными `offset_from_qr` и `radius`.

## Ассистент «Моттэл»

Инженерный ассистент прямо в приложении: разбор находок, список запчастей,
порядок оформления акта. Спрашивает бэкенд (`POST /api/chat`), в live-режиме
отвечает реальная LLM, в mock — сценарные ответы (`MottelScript.kt`).
Персонаж нарисован на Canvas: тёмный костюм, круглые очки, без картинок и
лишних зависимостей.

## Дизайн под одну руку

Телефон в правой руке — всё частое в нижней правой дуге большого пальца:

- главное действие — круглая кнопка 76 dp в правом нижнем углу;
- ассистент — рядом, чуть выше и левее (дистанция между целями больше 16 dp);
- статус оборудования — форма + текст + полоса цвета, а не «светофор»;
- цели не меньше 52–76 dp — попадать в перчатках.

## Демо без ARCore

ARCore не работает на эмуляторе и на части устройств. Приложение это определяет и
включает **SIM AR** — тот же сценарий поверх обычной камеры CameraX:

- маркеры узлов проецируются на экран по `offset_from_qr` (с учётом глубины `z`);
- оверлей дефектов, цвета маркеров, BottomSheet и PDF работают идентично;
- в шапке появляется бейдж `SIM AR`, чтобы никто не подумал, что AR «сломался».

Так питч можно показывать на ноутбуке через эмулятор, а на телефоне — в настоящем AR.

## Управление

- **Тап по маркеру / чипу узла** → карточка узла с дефектом и анализом.
- **Тап по области дефекта** на оверлее → сразу карточка этого дефекта.
- **«Разместить»** → ставит якорь в центр экрана, если авто-хит по плоскости не сработал.
- **Круглая кнопка «СКАН»** (внизу справа) → кадр и запрос на `/api/inspect`.
- **«Моттэл»** (рядом) → диалог с ассистентом.
- **Статус + «Зафиксировать акт»** → `/api/reports` → PDF.

## Структура

```
app/src/main/java/ru/cyber102/arinspector/
├── MainActivity.kt          навигация Сканер ⇄ AR
├── data/                    модели, Retrofit, DemoData, MottelScript
├── vm/                      InspectionViewModel (единое состояние)
├── ui/scanner/              CameraX + ML Kit
├── ui/ar/                   ARScene, маркеры, оверлей дефектов, SIM AR
├── ui/result/               BottomSheet с актом
├── ui/assistant/            диалог с Моттэлом
├── ui/components/           HUD-компоненты, Моттэл, кнопки большого пальца
├── ui/theme/                палитра и типографика
└── util/                    кадр → JPEG, генератор PDF
backend/server.py            API: mock/production, vision/LLM, /api/chat
backend/db.py                PostgreSQL repository
backend/object_storage.py    S3-compatible storage для фото/PDF
database/migrations/         versioned schema и Android QR catalog
demo/qr/                     готовые QR и лист для печати
docs/                        API, live-режим, дизайн, демо, онбординг агентов
```

## Документация

- [`docs/API.md`](docs/API.md) — контракт всех эндпоинтов.
- [`docs/LIVE_AI.md`](docs/LIVE_AI.md) — как подключить реальную модель за 5 минут.
- [`docs/AGENT_ONBOARDING.md`](docs/AGENT_ONBOARDING.md) — инструкция для ИИ-агентов.
- [`docs/DESIGN.md`](docs/DESIGN.md) — палитра, приёмы, идеи развития.
- [`docs/DEMO.md`](docs/DEMO.md) — сценарий питча на 90 секунд и киллер-фичи.
- [`docs/CHECKLIST.md`](docs/CHECKLIST.md) — что проверить за 20 минут до выступления.
- [`docs/AI_TEAM.md`](docs/AI_TEAM.md) — протокол для ИИ-моделей, подключённых к репозиторию.

## Ограничения и честность

- По умолчанию бэкенд отдаёт заранее подготовленные дефекты (`mock`) — это
  демонстрация контракта и страховка на сцене. С `LLM_BASE_URL`/`LLM_API_KEY`
  он же ходит в реальную vision-модель; приложение при этом не меняется.
- Ошибка live-модели в production возвращает `503`; подмена mock-ответом
  запрещена. В mock-профиле сеть и модель не требуются.
- Дефекты привязаны к экранным координатам кадра. При сильном смещении камеры
  оверлей нужно пересчитывать — для этого достаточно повторить сканирование.
- PDF-акт формируется на устройстве, подпись — ручная (место под неё в документе есть).
- В production акты и инспекции сохраняются в PostgreSQL; бинарные фото и PDF —
  во внешнем object storage.
