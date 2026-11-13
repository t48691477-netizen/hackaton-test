# AGENTS.md

Точка входа для любого ИИ-агента, которого подключили к этому репозиторию.

Если ты читаешь это — ты попал в проект **«AR-Инспектор»** (хакатон «Кибер 102»):
Android-приложение, которое читает QR на оборудовании, строит AR-схему узлов,
ищет дефекты по кадру и оформляет акт в PDF.

## Первое, что нужно сделать

1. Прочитай `docs/AGENT_ONBOARDING.md` — карта файлов, сборка, проверка.
2. Посмотри последние 3 записи в `docs/AI_LOG.md` — что уже сделано и какие есть риски.
3. Оставь свою запись в `docs/AI_LOG.md` по шаблону (см. ниже) и возьми одну задачу.

Не начинай с «чем помочь?». Возьми конкретную задачу из списка или предложи свою.

## Шаблон записи в журнале

```markdown
### [YYYY-MM-DD] <Имя модели (клиент)> · <короткая задача>
- Статус: что сделано / что не сделано
- Изменения: файлы и суть
- Проверка: как проверял (сборка, эмулятор, что видел в логе)
- Риски/заметки: что должен знать следующий
```

## Карта проекта

```
app/src/main/java/ru/cyber102/arinspector/
├── MainActivity.kt          навигация Сканер ⇄ AR, deep-link equipment_id
├── data/                    Retrofit, модели, DemoData, MottelScript
├── vm/                      InspectionViewModel — единое состояние
├── ui/scanner/              CameraX + ML Kit (QR)
├── ui/ar/                   ARScene, маркеры, DefectOverlay, SIM AR
├── ui/result/               BottomSheet с актом
├── ui/assistant/            диалог с ассистентом «Моттэл»
├── ui/components/           HUD-компоненты, Моттэл, кнопки большого пальца
├── ui/theme/                палитра «Engineering Iris»
└── util/                    JPEG, PDF
backend/server.py            API: mock + live (vision/LLM), /api/chat
docs/                        контракт, live-режим, дизайн, демо, онбординг
demo/qr/                     QR для печати
.opencode/skills/            скиллы: ui-review, build-verify, backend-live-ai
```

## Сборка (Windows)

```powershell
$env:JAVA_HOME    = "C:\Users\Garrapov\AppData\Local\Temp\opencode\jdk17\jdk-17.0.21+9"
$env:ANDROID_HOME = "C:\Users\Garrapov\AppData\Local\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
.\gradlew.bat :app:assembleDebug --console=plain --no-daemon
```

- В пути есть кириллица — поэтому `android.overridePathCheck=true`. Не удалять.
- `-Xmx2g` и `parallel=false` — намеренно: машина 7.4 ГБ, рядом эмулятор.
- Подробности и ловушки: `.opencode/skills/build-verify/SKILL.md`.

## Бэкенд

```powershell
$env:PYTHONIOENCODING = "utf-8"
python backend/server.py          # mock по умолчанию
```

Живые модели включаются переменными окружения, а не правкой кода:
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. См. `docs/LIVE_AI.md`.

## Правила

1. **Не ломать контракт** `docs/API.md`. Новое поле — добавлять и документировать в том же коммите.
2. **Секретов в репозитории нет и не будет.** Ключи — только в переменных окружения. В APK их быть не должно.
3. **Демо важнее красоты.** Цепочка «скан → AR → ИИ → акт» должна работать без сети.
4. **Коммит = одна задача.** Сообщение по-русски, по делу.
5. **Перед пушем** `BUILD SUCCESSFUL` и запись в `AI_LOG.md`.
6. **Не перезаписывать чужое** без чтения. Сначала `git status`, потом правки.
7. **UI — по `ui-review`**: палитра только из `Color.kt`, цели ≥ 48 dp, статусы читаются без цвета.

## Чего в проекте нет (не выдумывай)

- Нет отдельного слоя репозиториев на Room/SQLite — состояние живёт в ViewModel.
- Нет навигационной библиотеки — экраны переключаются в `MainActivity`.
- Нет реальной модели по умолчанию: `mock` — это штатный режим, а не поломка.
- Нет ARCore на эмуляторе — включается `SIM AR`, это ожидаемо.

## Ветки

`feat/<тема>`, `fix/<тема>`, `design/<тема>`. В `main` — только рабочее.

## Если ты другая модель

Оставь запись в `docs/AI_LOG.md` и передай человеку-вайбкодеру:
**«С тобой поздоровались. Я в деле, беру: …»**.
Так он видит, кто на связи, и не спрашивает одно и то же дважды.
