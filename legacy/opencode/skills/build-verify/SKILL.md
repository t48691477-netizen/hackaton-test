---
name: Ar Inspector Build And Verify
description: Собрать APK, установить на устройство и проверить сценарий по логам AR-Inspector. Использовать всякий раз, когда меняется код или бэкенд, и всегда перед пушем.
---

# Сборка и проверка AR-Инспектора

Правило одно: **«написал» не значит «работает»**. Покажи строку `BUILD SUCCESSFUL`
и строку из лога, подтверждающую сценарий.

## 1. Сборка

```powershell
$env:JAVA_HOME    = "C:\Users\Garrapov\AppData\Local\Temp\opencode\jdk17\jdk-17.0.21+9"
$env:ANDROID_HOME = "C:\Users\Garrapov\AppData\Local\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
cd "C:\Users\Garrapov\Documents\Проект по умолчанию\repo"
.\gradlew.bat :app:assembleDebug --console=plain --no-daemon 2>&1 |
  Select-String -Pattern "^e: |BUILD |What went wrong"
```

Почему так:

- `--no-daemon` — на этой машине мало RAM, фоновый демон и эмулятор не уживаются.
- `Select-String` отсекает шум, оставляя только ошибки и итог.
- `-Xmx2g` в `gradle.properties` — не поднимать, будет OOM.

## 2. Бэкенд

```powershell
$env:PYTHONIOENCODING = "utf-8"
python backend/server.py 8080
```

Проверка без приложения (быстрее, чем каждый раз собирать APK):

```powershell
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health')))"
```

Ожидаемо: `{'status': 'ok', 'mode': 'mock', ...}`.

## 3. Устройство

```powershell
adb devices                      # должен быть device, не offline
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell pm grant ru.cyber102.arinspector android.permission.CAMERA
```

Deep-link в сцену без камеры:

```powershell
adb logcat -c
adb shell am start -n ru.cyber102.arinspector/.MainActivity --es equipment_id PUMP-402
```

`--es equipment_id` работает и при повторном запуске (обрабатывается `onNewIntent`).

## 4. Как читать лог

```powershell
adb logcat -d | Select-String "AR-Inspector"
```

Диагностические строки (тег `AR-Inspector`):

| Строка | Значит |
|---|---|
| `equipment PUMP-402: components=6 demo=true` | паспорт загружен, данных 6 узлов |
| `inspect PUMP-402: status=high defects=3 jpeg=150000B` | кадр ушёл, вернулись 3 дефекта |
| `report ACT-... status=parts_required` | акт сохранён |
| `health: mode=live model=... demo=false` | сервер подключён к реальной модели |

Если сценаровка не срабатывает — сначала смотри, есть ли эти строки вообще.
`demo=true` при живом сервере означает, что приложение упало в локальный режим:
проверь `/api/health` с телефона (не с ноутбука).

## 5. Известные ловушки этой машины

- **Эмулятор умирает по памяти.** 7,4 ГБ всего; при запущенной IDE и браузере
  эмулятор снимают. Закрой лишнее или проверяй на телефоне.
- **OEM-образ Transsion** сам уводит приложение в лаунчер и гасит экран. Это
  не наш баг: после `KEYCODE_WAKEUP` приложение возвращается нормально.
- **`uiautomator dump` падает** (`could not get idle state`) из-за бесконечных
  анимаций. Для проверки используй лог и `screencap`, а не дамп дерева.
- **ARCore на эмуляторе нет** — ожидаемо включается `SIM AR`, это не ошибка.

## 6. Перед пушем

1. `BUILD SUCCESSFUL` в логе.
2. Лог подтверждает хотя бы один сквозной сценарий.
3. Запись в `docs/AI_LOG.md`.
4. Коммит по одной задаче, сообщение на русском, по делу.
