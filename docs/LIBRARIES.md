# Библиотеки и референсы дизайна

Отобрано и проверено 13.11.2026 (GitHub API, README, официальные страницы).
Ничего не добавлено в `build.gradle.kts` без причины — в таблице указано,
что взято, что отклонено и почему.

## Что взято

| Что | Источник | Лицензия | Как используется |
|---|---|---|---|
| Radix Colors (шкала) | [radix-ui/colors](https://github.com/radix-ui/colors) | MIT | значения фона, поверхностей, текста и акцента в `Color.kt` |
| Палитра Figma (источник вдохновения) | [figma.com/using-the-figma-brand](https://www.figma.com/using-the-figma-brand/) | — | только два HEX-оттенка (`#874FFF`, `#00B6FF`) для градиентов |
| Material Color Utilities | [material-foundation/material-color-utilities](https://github.com/material-foundation/material-color-utilities) | Apache-2.0 | ориентир для проверки контраста; код не подключён |
| Lucide (иконки) | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC / MIT | источник контурных SVG; конвертируем в VectorDrawable по мере надобности |
| Google Fonts | [google/fonts](https://github.com/google/fonts) | OFL по семействам | будущая офлайн-типографика через `res/font` |

## Что рассмотрено и отклонено

| Проект | Звёзды | Почему не взяли |
|---|---|---|
| [chrisbanes/haze](https://github.com/chrisbanes/haze) (blur/glass) | ~2,7k | На AR-превью `SurfaceView` не захватывается — blur сцены может не работать. Дорого по GPU на камере |
| [alexzhirkevich/compottie](https://github.com/alexzhirkevich/compottie) | ~700 | Отдельный движок ради анимаций, которые `Animatable`/`spring` делают бесплатно |
| [skydoves/FlexibleBottomSheet](https://github.com/skydoves/FlexibleBottomSheet) | ~1,1k | Немодальная панель полезна, но штатный Material 3 закрывает задачу; вернуться, если понадобится панель «в два уровня» |
| [jordond/MaterialKolor](https://github.com/jordond/MaterialKolor) | — | Генерация темы из seed — избыточно: палитра зафиксирована вручную |

## Почему палитра именно такая

Прошлая версия была «строительной»: сигнальный жёлтый как основной цвет и
уголки-визоры на каждой панели. В промышленном интерфейсе жёлтый — это
предупреждение, а не бренд.

Текущая схема:

- нейтральная холодная база (Slate 1/2/3) — помогает читать вложенность без рамок;
- один рабочий акцент (Iris 9 `#5B5BD6`) — основные действия;
- светлый вариант акцента (Iris 11 `#B1A9FF`) — мелкий текст, где тёмный акцент не читается;
- зелёный/амбер/красный — **только статусы**;
- оранжевый — **только цвет ржавчины** как материала, не как «ошибка».

Фирменные фиолетовый и синий Figma используются в градиентах, но логотип и
фирменную композицию Figma мы не воспроизводим (это прямо запрещено их
рекомендациями). Мы берём «родство по духу», а не имитацию.

## Как добавить библиотеку

1. Проверить лицензию и последний релиз на GitHub.
2. Оценить влияние на размер APK и на кадровый бюджет камеры.
3. Добавить в `app/build.gradle.kts` и в таблицу выше — **в одном коммите**.
4. Собрать и измерить: `Get-Item app\build\outputs\apk\debug\app-debug.apk`.
