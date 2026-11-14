# Как подключиться к проекту

Привет, коллега по цеху. Это AR-Инспектор: Android-приложение на Kotlin/Compose + Python mock-бэкенд, который отдаёт паспорт оборудования и "находки" дефектов.
Прочитай этот файл за 5 минут, посмотри `docs/API.md` — и ты в контексте. Дальше пиши в `docs/AI_LOG.md`, что сделал.
Проект живёт на дедлайне: собери, проверь в эмуляторе, и только потом оптимизируй.

---

## 2. Карта файлов

| Что | Где |
|---|---|
| Точка входа, deep-link `equipment_id` | `app/src/main/java/ru/cyber102/arinspector/MainActivity.kt` |
| Экраны (Compose) | `.../arinspector/ui/`: `scanner/ScannerScreen.kt`, `ar/ArScreen.kt` + `DefectOverlay.kt`, `result/ResultSheet.kt`, `settings/SettingsSheet.kt`, `components/Hud.kt`, `theme/` |
| Данные, сеть, модели | `.../arinspector/data/`: `Api.kt` (Retrofit), `EquipmentRepository.kt`, `Models.kt`, `DemoData.kt` (оффлайн-демо), `AppSettings.kt` (base URL) |
| ViewModel | `.../arinspector/vm/InspectionViewModel.kt` |
| Утилиты (JPEG, PDF) | `.../arinspector/util/`: `ImageUtils.kt`, `PdfAct.kt` |
| Mock-бэкенд | `backend/server.py` (stdlib, без зависимостей) |
| Документация | `docs/API.md` (контракт), `AI_LOG.md`, `AI_TEAM.md`, `DESIGN.md`, `DEMO.md`, `CHECKLIST.md` |
| QR для демо | `demo/qr/`: `PUMP-402.png`, `PUMP-118.png`, `VALVE-77.png`, `print.html` |

## 3. Сборка (Windows PowerShell)

```powershell
$env:JAVA_HOME   = "C:\Users\Garrapov\AppData\Local\Temp\opencode\jdk17\jdk-17.0.21+9"
$env:ANDROID_HOME = "C:\Users\Garrapov\AppData\Local\Android\Sdk"
cd "C:\Users\Garrapov\Documents\Проект по умолчанию\repo"
.\gradlew.bat :app:assembleDebug
```

- Путь к репозиторию содержит кириллицу — поэтому в `gradle.properties` стоит `android.overridePathCheck=true`. Не удаляй.
- Там же `org.gradle.jvmargs=-Xmx2g` и `parallel=false`: RAM мало, рядом крутится эмулятор. Не поднимай Xmx.
- APK: `app/build/outputs/apk/debug/app-debug.apk`.

## 4. Запуск бэкенда

```powershell
python backend/server.py     # порт 8080, слушает 0.0.0.0
```

- Эмулятор ходит на `http://10.0.2.2:8080/` (это и есть `BASE_URL` в `app/build.gradle.kts`).
- Телефон в той же Wi-Fi: в приложении → настройки → Base URL → `http://<IP-ноутбука>:8080/`.
- Нет сети вообще — включи Demo mode: экраны работают на `DemoData.kt`.

## 5. Проверка на эмуляторе

```powershell
& "$env:ANDROID_HOME\emulator\emulator.exe" -avd Medium_Phone_API_36.1
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell am start -n ru.cyber102.arinspector/.MainActivity --es equipment_id PUMP-402
adb logcat -s AR-Inspector
```

- Лог-тег один на весь проект: `AR-Inspector` (`InspectionViewModel.TAG`).
- ARCore на эмуляторе нет — приложение честно уходит в fallback-режим. Это нормально.

## 6. Правила

1. Не ломать контракт `docs/API.md`: новые поля — только добавлять и обновлять документ в том же коммите.
2. Не коммитить ключи, токены, `local.properties`. Секреты живут в переменных окружения.
3. Демо важнее красоты: рабочая цепочка "скан → AR → акт" приоритетнее анимаций.
4. Коммиты маленькие и с понятным сообщением, одна задача — один коммит.
5. Перед пушем `assembleDebug` должен быть зелёный (`BUILD SUCCESSFUL`).

## 7. Как оставить след

Добавь запись в `docs/AI_LOG.md` **сверху** (сразу после заголовка журнала), по шаблону:

```markdown
### [YYYY-MM-DD] <Имя модели (клиент)> · <короткая задача>
- Статус: что сделано / не сделано
- Изменения: файлы и суть
- Проверка: как проверял (сборка, эмулятор, что видел)
- Риски/заметки: что знает следующий
```

Ветки: `feat/<тема>` — новая функциональность, `fix/<тема>` — багфиксы, `design/<тема>` — UI/дизайн. В `main` не пушим напрямую.

## 8. Подключение к реальным моделям

Бэкенд сейчас отдаёт `"model": "demo-llm-vision"` — заглушку (сейчас она прописана как строка в трёх местах формирования ответа: строки ~89, ~152, ~176 `backend/server.py`). Чтобы подключить настоящую VLM:

- Переменные окружения (читать через `os.environ` в обработчике `POST /api/inspect`, `do_POST` в `backend/server.py`):
  - `LLM_BASE_URL` — адрес OpenAI-совместимого API;
  - `LLM_API_KEY` — ключ доступа;
  - `LLM_MODEL` — имя модели (вместо `demo-llm-vision`);
  - `LLM_TIMEOUT` — таймаут запроса, сек.
- Менять: только в `backend/server.py` и только через `os.environ` / `os.getenv`. Не хардкодь значения.
- **Никогда** не храни ключи в APK, `BuildConfig`, `AndroidManifest.xml` или `gradle.properties` — APK распаковывается за 10 секунд.
- Приложение всегда говорит только с бэкендом; провайдер модели — дело сервера.

## 9. Чек-лист «я только что подключился»

- [ ] Прочитал `docs/API.md` и `docs/AI_LOG.md` (последние 3 записи).
- [ ] Сборка `.\gradlew.bat :app:assembleDebug` даёт `BUILD SUCCESSFUL`.
- [ ] `python backend/server.py` отвечает: `curl http://localhost:8080/api/equipment/PUMP-402`.
- [ ] Приложение запускается с `--es equipment_id PUMP-402`, в `adb logcat -s AR-Inspector` есть загрузка паспорта.
- [ ] Знаю, где менять текст/данные демо: `DemoData.kt`, `demo/qr/`.
- [ ] Сделал ветку `feat/...` / `fix/...` и написал запись в `docs/AI_LOG.md`.
