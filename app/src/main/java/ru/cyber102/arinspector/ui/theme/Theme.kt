package ru.cyber102.arinspector.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val IndigoColors = darkColorScheme(
    primary = Indigo,
    onPrimary = TextHi,
    primaryContainer = IndigoDeep,
    onPrimaryContainer = TextHi,
    secondary = Aqua,
    onSecondary = Ink,
    secondaryContainer = InkHover,
    onSecondaryContainer = IndigoSoft,
    tertiary = Violet,
    onTertiary = Ink,
    background = Ink,
    onBackground = TextHi,
    surface = InkRaised,
    onSurface = TextHi,
    surfaceVariant = InkCard,
    onSurfaceVariant = TextMid,
    surfaceContainer = InkCard,
    surfaceContainerHigh = InkHover,
    outline = HairlineStrong,
    outlineVariant = Hairline,
    error = Danger,
    onError = Ink
)

/**
 * Типографика: крупные спокойные заголовки, моноширинный только для цифр и
 * идентификаторов. Прежний вариант делал «шильдиком» почти всё — читать было
 * тяжело.
 */
private val IndigoTypography = Typography(
    displayLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 40.sp,
        letterSpacing = (-0.5).sp,
        lineHeight = 46.sp
    ),
    displayMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 32.sp,
        letterSpacing = (-0.4).sp,
        lineHeight = 38.sp
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 23.sp,
        letterSpacing = (-0.2).sp,
        lineHeight = 29.sp
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 19.sp,
        letterSpacing = (-0.1).sp,
        lineHeight = 25.sp
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
        letterSpacing = 0.sp,
        lineHeight = 22.sp
    ),
    bodyLarge = TextStyle(
        fontSize = 15.5.sp,
        lineHeight = 23.sp,
        letterSpacing = 0.1.sp
    ),
    bodyMedium = TextStyle(
        fontSize = 13.5.sp,
        lineHeight = 20.sp,
        letterSpacing = 0.1.sp
    ),
    labelLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 14.5.sp,
        letterSpacing = 0.1.sp
    ),
    labelMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 11.5.sp,
        letterSpacing = 0.6.sp
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Medium,
        fontSize = 10.sp,
        letterSpacing = 0.8.sp
    )
)

private val HullShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

@Composable
fun ARInspectorTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = IndigoColors,
        typography = IndigoTypography,
        shapes = HullShapes,
        content = content
    )
}
