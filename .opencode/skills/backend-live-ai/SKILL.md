---
name: Ar Inspector Backend Live Ai
description: Переключить бэкенд между mock и live, подключить реальную vision/LLM-модель, проверить откат. Использовать при работе с /api/inspect, /api/chat, ключами и переменными окружения.
---

# Бэкенд и живые модели

## 1. Как устроено

```
Android  --Retrofit-->  backend/server.py  --HTTPS-->  vision/LLM провайдер
```

Приложение знает только `BASE_URL`. Всё, что касается моделей, живёт на сервере.
Это не стилистическое предпочтение: ключ в APK извлекается через `strings` за
минуту, поэтому секретов в клиенте нет вообще.

## 2. Два режима

`LIVE_MODE = bool(LLM_BASE_URL and LLM_API_KEY)` — одна формула в `server.py`.

| Условие | Режим | `/api/inspect` | `/api/chat` |
|---|---|---|---|
| переменные не заданы | `mock` | подготовленные дефекты | сценарий `MOTTEL_MOCK` |
| обе заданы | `live` | реальная модель | реальная модель |
| заданы, но модель не ответила | `mock` (тихий откат) | подготовленные дефекты | сценарий |

Тихий откат — главное свойство. Демо не должно падать из-за 500-й от провайдера.

## 3. Подключение модели (Windows PowerShell)

```powershell
$env:LLM_BASE_URL = "https://api.openai.com/v1"   # любой OpenAI-совместимый
$env:LLM_API_KEY  = "sk-..."                      # только в этой сессии
$env:LLM_MODEL    = "gpt-4o-mini"                 # модель со зрением
$env:LLM_TIMEOUT  = "45"
$env:PYTHONIOENCODING = "utf-8"
python backend/server.py 8080
```

Проверка:

```powershell
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health')))"
# mode=live, model=<LLM_MODEL>
```

В приложении бейдж в шапке сменится `DEMO` → `LIVE AI`.

## 4. Провайдеры и их особенности

| Провайдер | Совместимость | На что смотреть |
|---|---|---|
| OpenAI | нативная | актуальные имена моделей проверять в docs |
| OpenRouter | OpenAI-совместимый | формат ответа «плавает» между моделями |
| Together / vLLM / Ollama | `/v1` | проверь наличие vision-модели |
| Google Gemini | свой формат | нужен свой адаптер в `call_llm()` |
| Anthropic | свой формат | нужен свой адаптер |

Не-OpenAI провайдер = переписать тело **одной** функции `call_llm()`.
Контракт `/api/inspect` и приложение при этом не меняются.

## 5. Проверка отката (обязательна перед демо)

Подними второй сервер с заведомо мёртвым адресом:

```powershell
$env:LLM_BASE_URL = "http://127.0.0.1:9/v1"
$env:LLM_API_KEY  = "fake"
$env:LLM_MODEL    = "fake-vision"
python backend/server.py 8090
```

Ожидаемо: `health` → `live`, а `POST /api/inspect` и `/api/chat` возвращают
`200` с mock-данными. В логе — `LIVE FAILED (...) -> mock`.

## 6. Контракт ответа модели

Модель обязана вернуть JSON:

```json
{
  "status": "ok|medium|high",
  "analysis": "…",
  "defects": [
    { "id": "D-LIVE-1", "node_id": "C3", "type": "rust",
      "title": "…", "confidence": 0.9, "severity": "high",
      "bbox": [0.1, 0.2, 0.4, 0.5],
      "analysis": "…", "recommendation": "…" }
  ]
}
```

`bbox` — доли кадра 0..1. Сервер сам превращает его в `polygon` и нормализует
координаты, чтобы оверлей лёг 1:1 на экран. Если модель вернула мусор —
`extract_json` вырезает JSON из ```-блоков, а при провале срабатывает откат.

## 7. Что нельзя

- Класть ключ в `BuildConfig`, `strings.xml`, `gradle.properties`, `local.properties`.
- Коммитить `.env`.
- Показывать `LIVE AI`, если модель не отвечает (это ложь жюри).
