package ru.cyber102.arinspector.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudCyan
import ru.cyber102.arinspector.ui.theme.SafetyYellow

/**
 * Моттэл — инженерный ассистент.
 *
 * Стилизованный контурный персонаж: тёмный костюм, светлая рубашка, галстук и
 * круглые очки. Рисуется примитивами Canvas, поэтому весит ноль зависимостей
 * и не грузит память на экране с камерой.
 *
 * @param speaking лёгкая пульсация «линз» — признак, что ассистент думает.
 */
@Composable
fun MottelAvatar(
    modifier: Modifier = Modifier,
    size: Dp = 48.dp,
    accent: Color = SafetyYellow,
    speaking: Boolean = false
) {
    val transition = rememberInfiniteTransition(label = "mottel")
    val pulse by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "mottel-pulse"
    )

    Canvas(modifier = modifier.size(size)) {
        val w = this.size.width
        val h = this.size.height
        val stroke = w * 0.045f
        val ink = Color(0xFFEAF2F5)
        val suit = Color(0xFF1C262C)

        fun p(x: Float, y: Float) = Offset(w * x, h * y)

        // Силуэт: плечи и пиджак.
        val shoulders = Path().apply {
            moveTo(w * 0.10f, h * 1.02f)
            cubicTo(w * 0.12f, h * 0.72f, w * 0.34f, h * 0.64f, w * 0.5f, h * 0.64f)
            cubicTo(w * 0.66f, h * 0.64f, w * 0.88f, h * 0.72f, w * 0.90f, h * 1.02f)
            close()
        }
        drawPath(shoulders, suit)
        drawPath(shoulders, ink, style = Stroke(stroke, cap = StrokeCap.Round))

        // Рубашка и галстук.
        val shirt = Path().apply {
            moveTo(w * 0.42f, h * 0.66f)
            lineTo(w * 0.5f, h * 0.80f)
            lineTo(w * 0.58f, h * 0.66f)
            close()
        }
        drawPath(shirt, Color(0xFFDCE6EA))
        val tie = Path().apply {
            moveTo(w * 0.5f, h * 0.70f)
            lineTo(w * 0.545f, h * 0.78f)
            lineTo(w * 0.515f, h * 0.96f)
            lineTo(w * 0.485f, h * 0.96f)
            lineTo(w * 0.455f, h * 0.78f)
            close()
        }
        drawPath(tie, accent)

        // Лацканы.
        drawLine(ink, p(0.40f, 0.66f), p(0.44f, 0.98f), stroke * 0.8f, StrokeCap.Round)
        drawLine(ink, p(0.60f, 0.66f), p(0.56f, 0.98f), stroke * 0.8f, StrokeCap.Round)

        // Шея и голова.
        drawLine(ink, p(0.47f, 0.60f), p(0.47f, 0.68f), stroke, StrokeCap.Round)
        drawLine(ink, p(0.53f, 0.60f), p(0.53f, 0.68f), stroke, StrokeCap.Round)
        drawCircle(ink, radius = w * 0.205f, center = p(0.5f, 0.42f), style = Stroke(stroke))
        drawCircle(Color(0xFF0D1418), radius = w * 0.185f, center = p(0.5f, 0.42f))

        // Причёска — короткая, с пробором.
        val hair = Path().apply {
            moveTo(w * 0.31f, h * 0.40f)
            cubicTo(w * 0.30f, h * 0.20f, w * 0.70f, h * 0.20f, w * 0.69f, h * 0.40f)
            cubicTo(w * 0.64f, h * 0.32f, w * 0.52f, h * 0.30f, w * 0.44f, h * 0.36f)
            cubicTo(w * 0.40f, h * 0.39f, w * 0.36f, h * 0.40f, w * 0.31f, h * 0.40f)
            close()
        }
        drawPath(hair, ink)

        // Круглые очки — главный акцент.
        val lensRadius = w * 0.088f
        val rim = if (speaking) accent.copy(alpha = 0.6f + 0.4f * pulse) else ink
        drawCircle(
            color = HudCyan.copy(alpha = 0.18f + 0.22f * (if (speaking) pulse else 0f)),
            radius = lensRadius,
            center = p(0.435f, 0.435f)
        )
        drawCircle(
            color = HudCyan.copy(alpha = 0.18f + 0.22f * (if (speaking) pulse else 0f)),
            radius = lensRadius,
            center = p(0.565f, 0.435f)
        )
        drawCircle(rim, lensRadius, p(0.435f, 0.435f), style = Stroke(stroke))
        drawCircle(rim, lensRadius, p(0.565f, 0.435f), style = Stroke(stroke))
        drawLine(rim, p(0.523f, 0.435f), p(0.477f, 0.435f), stroke)
        drawLine(rim, p(0.347f, 0.425f), p(0.315f, 0.415f), stroke * 0.9f)
        drawLine(rim, p(0.653f, 0.425f), p(0.685f, 0.415f), stroke * 0.9f)

        // Блики на линзах.
        drawCircle(
            Color.White.copy(alpha = 0.75f),
            radius = w * 0.018f,
            center = p(0.405f, 0.405f)
        )
        drawCircle(
            Color.White.copy(alpha = 0.75f),
            radius = w * 0.018f,
            center = p(0.535f, 0.405f)
        )

        // Спокойная линия рта.
        drawArc(
            color = ink,
            startAngle = 20f,
            sweepAngle = 140f,
            useCenter = false,
            topLeft = Offset(w * 0.455f, h * 0.49f),
            size = Size(w * 0.09f, h * 0.055f),
            style = Stroke(stroke * 0.85f, cap = StrokeCap.Round)
        )

        // Бейдж инженера на лацкане.
        drawLine(accent, p(0.615f, 0.86f), p(0.655f, 0.86f), stroke * 1.2f, StrokeCap.Round)
    }
}

/** Компактный аватар в круге с фирменной подсветкой — для шапки и кнопки. */
@Composable
fun MottelBadge(
    modifier: Modifier = Modifier,
    size: Dp = 44.dp,
    accent: Color = SafetyYellow,
    speaking: Boolean = false
) {
    Box(modifier = modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(size)) {
            val r = this.size.minDimension / 2f
            drawCircle(HudBlack.copy(alpha = 0.92f), r, center)
            drawCircle(
                accent.copy(alpha = 0.85f),
                r - 1.dp.toPx(),
                center,
                style = Stroke(1.2.dp.toPx())
            )
        }
        MottelAvatar(
            size = size * 0.86f,
            accent = accent,
            speaking = speaking
        )
    }
}
