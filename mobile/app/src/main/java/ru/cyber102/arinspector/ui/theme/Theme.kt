package ru.cyber102.arinspector.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp

object PromScanShapesTokens {
    val Card = RoundedCornerShape(20.dp)
    val Control = RoundedCornerShape(12.dp)
    val Chip = RoundedCornerShape(50)
}

private val LightColorScheme = lightColorScheme(
    primary = KstColors.Accent,
    onPrimary = KstColors.White,
    primaryContainer = KstColors.AccentTint,
    onPrimaryContainer = KstColors.NavyDark,
    secondary = KstColors.NavyDark,
    onSecondary = KstColors.White,
    secondaryContainer = KstColors.AccentTint,
    onSecondaryContainer = KstColors.NavyDark,
    background = KstColors.Background,
    onBackground = KstColors.TextPrimary,
    surface = KstColors.Surface,
    onSurface = KstColors.TextPrimary,
    surfaceVariant = KstColors.Background,
    onSurfaceVariant = KstColors.TextSecondary,
    outline = KstColors.Border,
    outlineVariant = KstColors.Border,
    error = KstColors.Error,
    onError = KstColors.White,
    errorContainer = KstColors.ErrorTint,
    onErrorContainer = KstColors.Error
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(24.dp)
)

@Composable
fun PromScanTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = PromScanTypography,
        shapes = AppShapes,
        content = content
    )
}
