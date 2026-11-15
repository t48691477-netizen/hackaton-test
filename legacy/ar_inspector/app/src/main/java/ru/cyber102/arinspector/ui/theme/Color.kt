package ru.cyber102.arinspector.ui.theme

import androidx.compose.ui.graphics.Color

// ---------------------------------------------------------------------------
// Палитра «Engineering Iris»
//
// Основа — нейтральная холодная шкала Radix Slate + акцент Radix Iris.
// Фирменные оттенки взяты из официального архива бренда Figma (SVG, не по
// скриншоту): фиолетовый #874FFF и синий #00B6FF. Используем ТОЛЬКО цвета
// как источник вдохновения — никаких логотипов и фирменной композиции Figma.
//
// Источники значений:
//   Radix dark palette  https://github.com/radix-ui/colors/blob/main/src/dark.ts
//   Figma brand assets  https://www.figma.com/using-the-figma-brand/
//
// Жёлтый остаётся только у Warning. Это осознанно: на стройке жёлтый —
// сигнальный, поэтому основной цвет интерфейса он быть не может.
// ---------------------------------------------------------------------------

// Фон и поверхности: 3 уровня, чтобы вложенность читалась без рамок.
val Ink = Color(0xFF111113)          // Slate 1
val InkRaised = Color(0xFF18191B)    // Slate 2
val InkCard = Color(0xFF212225)      // Slate 3
val InkHover = Color(0xFF292A2E)     // Slate 4

// Контуры.
val Hairline = Color(0xFF43484E)     // Slate 7
val HairlineStrong = Color(0xFF5A6169)

// Акценты.
val Indigo = Color(0xFF5B5BD6)       // Iris 9  — заливки и крупные элементы
val IndigoDeep = Color(0xFF4747C2)   // Iris 8  — нажатие
val IndigoSoft = Color(0xFFB1A9FF)   // Iris 11 — мелкий текст на тёмном
val Violet = Color(0xFF874FFF)       // брендовый фиолетовый (gradients)
val Sky = Color(0xFF00B6FF)          // брендовый синий (gradients)
val Aqua = Color(0xFF4CC38A)         // технический акцент «живого» режима

// Состояния.
val Success = Color(0xFF3DD68C)      // Green 11
val Warning = Color(0xFFFFC53D)      // Amber 9
val Danger = Color(0xFFFF9592)       // Red 11
val DangerFill = Color(0xFFE5484D)   // Red 9 — заливки
val Rust = Color(0xFFA35829)         // Orange 8 — цвет ржавчины как материала

// Текст.
val TextHi = Color(0xFFEDEEF0)       // Slate 12
val TextMid = Color(0xFFB0B4BA)      // Slate 11
val TextLow = Color(0xFF7C8289)      // между Slate 10 и 11

// ---------------------------------------------------------------------------
// Совместимость со старыми именами. Ничего не удаляем сразу: в проекте сотни
// вызовов, и тихая замена всех сразу — верный способ получить «полу-редизайн».
// ---------------------------------------------------------------------------
val Accent = Indigo
val HudBlack = Ink
val HudSurface = InkRaised
val HudPanelHigh = InkCard
val HudLine = Hairline
val HudCyan = Aqua
val HudGreen = Success
val HudAmber = Warning
val HudRed = Danger
val TextPrimary = TextHi
val TextMuted = TextMid
val TextDim = TextLow

@Deprecated("Основной цвет теперь Indigo. Жёлтый оставлен только для Warning.")
val SafetyYellow = Warning
