# Контракт API — AR-Инспектор

Базовый URL задаётся в приложении (экран «Сеть»). По умолчанию `http://10.0.2.2:8080/`
(эмулятор → хост-машина). Все тела — JSON UTF-8.

## 1. `GET /api/equipment/{id}`

Вызывается после распознавания QR. `{id}` — нормализованный идентификатор (`PUMP-402`).

```json
{
  "id": "PUMP-402",
  "name": "Насосный агрегат ЦНС 38-220",
  "location": "Цех №4 · Насосная станция, поз. 12",
  "components": [
    {
      "id": "C3",
      "name": "Фланец №3",
      "offset_from_qr": { "x": -0.28, "y": 0.44, "z": -0.04 },
      "radius": 0.20,
      "description": "Фланцевое соединение, 8 болтов М20"
    }
  ]
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `components[].offset_from_qr` | `{x,y,z}` | Смещение узла от QR-якоря, **метры**. Ось Y — вверх, Z — от плоскости QR к наблюдателю |
| `components[].radius` | float | Радиус зоны узла, м. Дефект с `offset_from_qr` внутри радиуса привязывается к узлу |

Поля `manufacturer`, `model`, `serial_number`, `specs` и `passport_components`
могут присутствовать у оборудования с импортированным паспортом. `specs` и
`passport_components` содержат подтверждённые текстовые характеристики, но не
AR-геометрию. Они не добавляются в `components`: AR-узлом считается только
запись из `equipment_nodes` с заданными `offset_from_qr` и `radius`.

### 1.1 `GET /api/equipment`

Возвращает каталог для ручного выбора оборудования:

```json
{
  "equipment": [
    { "id": "PUMP-402", "name": "Насосный агрегат ЦНС 38-220" },
    { "id": "21031004-1", "name": "Насос AMS PCP60S12/3 №1" }
  ]
}
```

В production каталог читается из PostgreSQL. Для AMS ID ответа пока равен
серийному номеру, пока для оборудования не утверждён отдельный `qr_id`.

### 1.2 `GET /api/equipment/{id}/documents`

Возвращает метаданные документов оборудования, не включая бинарные данные и
локальный путь источника:

```json
{
  "documents": [
    {
      "id": 1,
      "file_name": "1) Насос №1 ПС.pdf",
      "document_type": "passport",
      "mime_type": "application/pdf",
      "byte_size": 734003,
      "sha256": "<64 lowercase hex characters>",
      "imported_at": "2026-11-15T10:00:00Z",
      "content_available": true
    }
  ]
}
```

Для metadata-only записи `content_available` равно `false`, а размер,
checksum и время импорта равны `null`. Неизвестное оборудование даёт `404`;
сбой PostgreSQL в production даёт `503`.

### 1.3 `GET /api/equipment/{id}/documents/{document_id}`

Возвращает бинарное содержимое документа непосредственно из
`promscan.equipment_documents.content` (`bytea`). Успешный ответ содержит
`Content-Type`, `Content-Disposition`, `ETag` с SHA-256,
`Cache-Control: private, no-store` и `X-Content-Type-Options: nosniff`.
Документ без импортированного содержимого и неизвестный ID документа дают
`404`. Этот маршрут не читает `source_path` и не обращается к Яндекс.Диску.

## 2. `POST /api/inspect`

Кадр отправляется как JPEG → Base64 (без префикса `data:`).
Кадр **повёрнут в портрет и центрально обрезан под аспект экрана** — поэтому
нормализованные координаты ответа ложатся на Canvas 1:1.

```json
{
  "equipment_id": "PUMP-402",
  "image_base64": "/9j/4AAQSkZJRgABAQ...",
  "screen_aspect": 0.462,
  "image_width": 960,
  "image_height": 2077
}
```

Ответ:

```json
{
  "status": "high",
  "defects": [
    {
      "id": "D-402-1",
      "node_id": "C3",
      "type": "rust",
      "title": "Коррозия фланцевого соединения",
      "confidence": 0.94,
      "severity": "high",
      "polygon": [{ "x": 0.54, "y": 0.345 }, { "x": 0.66, "y": 0.30 }],
      "bbox": [0.54, 0.30, 0.79, 0.55],
      "analysis": "Инженерный разбор от LLM…",
      "recommendation": "Что делать…"
    }
  ],
  "analysis": "Общий вывод по кадру",
  "inspection_id": "8c4b7c1d-7c67-4e48-a4d0-6b4b1d8a9b2e",
  "inspected_at": "2026-11-13T10:42:00Z",
  "model": "vision-v1"
}
```

`inspection_id` возвращается production-backend после записи результата в
PostgreSQL. В mock-профиле поле может отсутствовать. В production исходный
JPEG сохраняется во внешнем S3-compatible object storage; PostgreSQL хранит
только метаданные и ссылку на объект.

Правила отображения:

- `polygon` / `bbox` — **нормализованные** координаты 0..1 относительно экрана.
- `type = "rust"` → заливка полупрозрачным красным + штриховка.
- `type = "crack"` → пунктирная рамка по `bbox`.
- `status = high|critical` **или** дефект привязан к узлу (`node_id` либо попадание
  `offset_from_qr` в `radius`) → 3D-маркер узла становится красным.

## 3. `POST /api/reports`

```json
{
  "equipment_id": "PUMP-402",
  "node_id": "C3",
  "defect_id": "D-402-1",
  "defect_title": "Коррозия фланцевого соединения",
  "status": "parts_required",
  "comment": "Заказать прокладку, повторный осмотр в пятницу",
  "created_at": "2026-11-13T10:44:12Z",
  "inspection_id": "8c4b7c1d-7c67-4e48-a4d0-6b4b1d8a9b2e",
  "idempotency_key": "8fc6d94f-2a55-4de6-8b8f-5c2a2b9b7a10"
}
```

`status`: `fixed_on_site` | `parts_required` | `false_positive`.

Ответ:

```json
{ "report_id": "ACT-261113-A1B2", "status": "parts_required", "created_at": "2026-11-13T10:44:12Z" }
```

`report_id` печатается в PDF-акте и в BottomSheet.

`idempotency_key` необязателен в mock/demo. В production он рекомендуется для
повторной отправки после сетевого сбоя: повтор с тем же ключом и тем же телом
возвращает исходный акт, а повтор с другим телом получает `409`.

## 4. `GET /api/reports`

```json
{ "reports": [ { "report_id": "ACT-261113-A1B2", "equipment_id": "PUMP-402", "status": "parts_required" } ] }
```

## 5. `GET /api/health`

```json
{
  "status": "ok",
  "mode": "live",
  "profile": "production",
  "persistence": "postgresql",
  "database": "postgresql",
  "object_storage": "s3",
  "ai": "live",
  "model": "gpt-4o-mini",
  "time": "2026-11-13T10:42:00Z"
}
```

`mode`: `mock` | `live`. Приложение показывает `LIVE AI` при `live`,
`DEMO` при `mock`. Подробнее — [`LIVE_AI.md`](LIVE_AI.md).

`profile`: `mock` | `production`. В production неизвестное оборудование
возвращает `404`. Если PostgreSQL, S3-compatible storage или live AI не готовы,
health отвечает `503` со статусом `degraded`; production API не подменяет
данные демо-каталогом.

## 6. `POST /api/reports/{report_id}/document`

Загружает PDF, сформированный Android локально. Бинарное содержимое передаётся
в Base64, а в PostgreSQL остаются только `object_key`, MIME-тип, размер,
SHA-256 и связь с актом.

```json
{
  "mime_type": "application/pdf",
  "file_base64": "JVBERi0xLjQK..."
}
```

В production принимается только PDF; при недоступном S3-compatible storage
endpoint отвечает `503`. Повторная загрузка того же PDF идемпотентна, другой
PDF для уже прикреплённого акта получает `409`. В mock-профиле endpoint
отвечает `501`, чтобы не создавать ложное ощущение серверного хранения.

## 7. `POST /api/chat` — ассистент «Моттэл»

```json
{
  "message": "Что делать с находками?",
  "equipment_id": "PUMP-402",
  "history": [
    { "role": "user", "text": "…" },
    { "role": "mottel", "text": "…" }
  ]
}
```

```json
{ "reply": "Начинай с фланца №3: …", "model": "gpt-4o-mini" }
```

`model` в mock-режиме — `mock-assistant`. История обрезается последними 8 репликами.

## Поведение при недоступном бэкенде

При включённом Android **Демо-режиме** приложение использует локальные
`DemoData.kt` и `MottelScript.kt`. При выключенном Демо-режиме сетевые ошибки не
подменяются локальными данными: приложение показывает понятную ошибку, чтобы
production не выдавал mock-результат как настоящий. PDF-паспорта оборудования
хранятся в PostgreSQL `bytea`; бинарные фото осмотров и PDF-акты хранятся во
внешнем S3-compatible object storage.
