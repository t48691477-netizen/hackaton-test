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
  "inspected_at": "2026-11-13T10:42:00Z",
  "model": "vision-v1"
}
```

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
  "created_at": "2026-11-13T10:44:12Z"
}
```

`status`: `fixed_on_site` | `parts_required` | `false_positive`.

Ответ:

```json
{ "report_id": "ACT-261113-A1B2", "status": "parts_required", "created_at": "2026-11-13T10:44:12Z" }
```

`report_id` печатается в PDF-акте и в BottomSheet.

## 4. `GET /api/reports`

```json
{ "reports": [ { "report_id": "ACT-261113-A1B2", "equipment_id": "PUMP-402", "status": "parts_required" } ] }
```

## 5. `GET /api/health`

```json
{ "status": "ok", "mode": "live", "model": "gpt-4o-mini", "time": "2026-11-13T10:42:00Z" }
```

`mode`: `mock` | `live`. Приложение показывает `LIVE AI` при `live`,
`DEMO` при `mock`. Подробнее — [`LIVE_AI.md`](LIVE_AI.md).

## 6. `POST /api/chat` — ассистент «Моттэл»

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

Приложение **никогда не падает** из-за сети: при ошибке/Live-режиме выключенном
ответ собирается локально (`DemoData.kt`, `MottelScript.kt`), а в HUD появляется
бейдж `DEMO`.
