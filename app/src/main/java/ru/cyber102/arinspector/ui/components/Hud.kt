package ru.cyber102.arinspector.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudCyan
import ru.cyber102.arinspector.ui.theme.HudLine
import ru.cyber102.arinspector.ui.theme.HudSurface
import ru.cyber102.arinspector.ui.theme.SafetyYellow
import ru.cyber102.arinspector.ui.theme.TextDim
import ru.cyber102.arinspector.ui.theme.TextMuted

/** Рамка в стиле HUD: тёмная заливка, тонкий контур и угловые скобки. */
fun Modifier.hudFrame(
    accent: Color = HudCyan,
    fill: Color = HudSurface.copy(alpha = 0.94f),
    cornerLength: Dp = 14.dp,
    strokeWidth: Dp = 1.dp,
    bracketWidth: Dp = 2.dp
): Modifier = drawBehind {
    drawRect(fill)
    drawRect(HudLine.copy(alpha = 0.9f), style = Stroke(strokeWidth.toPx()))
    val len = cornerLength.toPx()
    val width = bracketWidth.toPx()
    val w = size.width
    val h = size.height
    drawLine(accent, Offset(0f, 0f), Offset(len, 0f), width)
    drawLine(accent, Offset(0f, 0f), Offset(0f, len), width)
    drawLine(accent, Offset(w, 0f), Offset(w - len, 0f), width)
    drawLine(accent, Offset(w, 0f), Offset(w, len), width)
    drawLine(accent, Offset(0f, h), Offset(len, h), width)
    drawLine(accent, Offset(0f, h), Offset(0f, h - len), width)
    drawLine(accent, Offset(w, h), Offset(w - len, h), width)
    drawLine(accent, Offset(w, h), Offset(w, h - len), width)
}

@Composable
fun HudPanel(
    modifier: Modifier = Modifier,
    accent: Color = HudCyan,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .hudFrame(accent = accent)
            .padding(14.dp)
    ) {
        content()
    }
}

@Composable
fun StatusPill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    filled: Boolean = false
) {
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(4.dp))
            .background(if (filled) color else color.copy(alpha = 0.12f))
            .border(1.dp, color.copy(alpha = 0.65f), RoundedCornerShape(4.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier
                .size(5.dp)
                .background(if (filled) HudBlack else color, CircleShape)
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = text.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = if (filled) HudBlack else color,
            maxLines = 1
        )
    }
}

@Composable
fun MonoLabel(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = TextMuted
) {
    Text(
        text = text.uppercase(),
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall,
        color = color
    )
}

@Composable
fun ConfidenceBar(
    value: Float,
    color: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(4.dp)
            .background(HudLine)
    ) {
        Box(
            Modifier
                .fillMaxWidth(value.coerceIn(0f, 1f))
                .fillMaxHeight()
                .background(color)
        )
    }
}

/** Бегущая сканирующая линия. */
@Composable
fun ScanLine(
    modifier: Modifier = Modifier,
    color: Color = HudCyan
) {
    val transition = rememberInfiniteTransition(label = "scanline")
    val progress by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "scanline-progress"
    )
    Box(
        modifier = modifier.drawBehind {
            val y = size.height * progress
            val glow = 48.dp.toPx()
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(Color.Transparent, color.copy(alpha = 0.28f)),
                    startY = (y - glow).coerceAtLeast(0f),
                    endY = y
                ),
                topLeft = Offset(0f, (y - glow).coerceAtLeast(0f)),
                size = Size(size.width, glow.coerceAtMost(y))
            )
            drawLine(
                color = color.copy(alpha = 0.95f),
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 2.dp.toPx()
            )
        }
    )
}

@Composable
fun PrimaryAction(
    text: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    Button(
        onClick = onClick,
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp),
        enabled = enabled,
        shape = RoundedCornerShape(10.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = SafetyYellow,
            contentColor = HudBlack,
            disabledContainerColor = HudLine,
            disabledContentColor = TextDim
        )
    ) {
        if (icon != null) {
            androidx.compose.material3.Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(20.dp)
            )
            Spacer(Modifier.width(10.dp))
        }
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
fun KeyValueRow(
    key: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = MaterialTheme.colorScheme.onSurface
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = key,
            style = MaterialTheme.typography.labelSmall,
            color = TextMuted
        )
        Spacer(Modifier.width(12.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium.copy(
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp
            ),
            color = valueColor,
            maxLines = 2
        )
    }
}

@Composable
fun SectionTitle(
    index: String,
    title: String,
    modifier: Modifier = Modifier,
    color: Color = SafetyYellow
) {
    Row(modifier = modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = index,
            style = MaterialTheme.typography.labelSmall,
            color = color
        )
        Spacer(Modifier.width(8.dp))
        Box(
            Modifier
                .width(14.dp)
                .height(1.dp)
                .background(color.copy(alpha = 0.7f))
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = title.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            color = color
        )
        Spacer(Modifier.weight(1f))
    }
}

@Composable
fun HudDivider(modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(HudLine.copy(alpha = 0.7f))
    )
}

@Composable
fun <T> SegmentedChoice(
    options: List<Pair<T, String>>,
    selected: T?,
    modifier: Modifier = Modifier,
    onSelect: (T) -> Unit
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (value, label) ->
            val isSelected = value == selected
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (isSelected) SafetyYellow.copy(alpha = 0.10f) else HudSurface)
                    .border(
                        width = 1.dp,
                        color = if (isSelected) SafetyYellow else HudLine,
                        shape = RoundedCornerShape(8.dp)
                    )
                    .clickable { onSelect(value) }
                    .padding(horizontal = 12.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(16.dp)
                        .border(
                            1.5.dp,
                            if (isSelected) SafetyYellow else TextDim,
                            CircleShape
                        )
                        .padding(4.dp)
                        .background(
                            if (isSelected) SafetyYellow else Color.Transparent,
                            CircleShape
                        )
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isSelected) MaterialTheme.colorScheme.onSurface else TextMuted
                )
            }
        }
    }
}
