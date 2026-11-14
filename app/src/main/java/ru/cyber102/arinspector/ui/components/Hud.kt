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
import ru.cyber102.arinspector.ui.theme.Aqua
import ru.cyber102.arinspector.ui.theme.Hairline
import ru.cyber102.arinspector.ui.theme.Ink
import ru.cyber102.arinspector.ui.theme.InkCard
import ru.cyber102.arinspector.ui.theme.Indigo
import ru.cyber102.arinspector.ui.theme.IndigoSoft
import ru.cyber102.arinspector.ui.theme.TextHi
import ru.cyber102.arinspector.ui.theme.TextLow
import ru.cyber102.arinspector.ui.theme.TextMid

/**
 * Карточка интерфейса.
 *
 * Раньше это была «панель с уголками-визирами» — приём из видоискателя,
 * который на каждом экране превращал интерфейс в строительный стенд.
 * Теперь: мягкое скругление, слоистая поверхность, тонкая линия-контур и
 * опциональная цветная полоса слева для смыслового акцента.
 */
fun Modifier.hudFrame(
    accent: Color = Indigo,
    fill: Color = InkCard,
    cornerLength: Dp = 0.dp,
    strokeWidth: Dp = 1.dp,
    bracketWidth: Dp = 0.dp
): Modifier = this
    .clip(RoundedCornerShape(14.dp))
    .background(fill)
    .border(strokeWidth, Hairline, RoundedCornerShape(14.dp))

@Composable
fun HudPanel(
    modifier: Modifier = Modifier,
    accent: Color = Indigo,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(InkCard)
            .border(1.dp, Hairline, RoundedCornerShape(14.dp))
    ) {
        // Смысловая полоса слева: единственный цветной акцент карточки.
        Box(
            Modifier
                .align(Alignment.CenterStart)
                .width(3.dp)
                .fillMaxHeight()
                .background(accent)
        )
        Box(Modifier.padding(start = 14.dp, top = 14.dp, end = 14.dp, bottom = 14.dp)) {
            content()
        }
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
            .clip(RoundedCornerShape(999.dp))
            .background(if (filled) color else color.copy(alpha = 0.14f))
            .border(1.dp, color.copy(alpha = if (filled) 0f else 0.35f), RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier
                .size(5.dp)
                .background(if (filled) Ink else color, CircleShape)
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = text.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = if (filled) Ink else color,
            maxLines = 1
        )
    }
}

@Composable
fun MonoLabel(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = TextMid
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
            .height(6.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(Hairline)
    ) {
        Box(
            Modifier
                .fillMaxWidth(value.coerceIn(0.02f, 1f))
                .fillMaxHeight()
                .background(
                    Brush.horizontalGradient(
                        listOf(color.copy(alpha = 0.75f), color)
                    )
                )
        )
    }
}

@Composable
fun ScanLine(
    modifier: Modifier = Modifier,
    color: Color = Aqua
) {
    val transition = rememberInfiniteTransition(label = "scanline")
    val progress by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2600, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "scanline-progress"
    )
    Box(
        modifier = modifier.drawBehind {
            val y = size.height * progress
            val glow = 64.dp.toPx()
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(Color.Transparent, color.copy(alpha = 0.22f)),
                    startY = (y - glow).coerceAtLeast(0f),
                    endY = y
                ),
                topLeft = Offset(0f, (y - glow).coerceAtLeast(0f)),
                size = Size(size.width, glow.coerceAtMost(y))
            )
            drawLine(
                color = color.copy(alpha = 0.9f),
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 1.5.dp.toPx()
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
            .height(54.dp),
        enabled = enabled,
        shape = RoundedCornerShape(14.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = Indigo,
            contentColor = TextHi,
            disabledContainerColor = Hairline,
            disabledContentColor = TextLow
        )
    ) {
        if (icon != null) {
            androidx.compose.material3.Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(19.dp)
            )
            Spacer(Modifier.width(10.dp))
        }
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
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
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = key,
            style = MaterialTheme.typography.bodyMedium,
            color = TextMid
        )
        Spacer(Modifier.width(12.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium.copy(
                fontFamily = FontFamily.Monospace,
                fontSize = 12.5.sp
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
    color: Color = IndigoSoft
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
                .width(16.dp)
                .height(1.dp)
                .background(color.copy(alpha = 0.5f))
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
            .background(Hairline)
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
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (isSelected) Indigo.copy(alpha = 0.14f) else Ink)
                    .border(
                        width = 1.dp,
                        color = if (isSelected) Indigo else Hairline,
                        shape = RoundedCornerShape(12.dp)
                    )
                    .clickable { onSelect(value) }
                    .padding(horizontal = 14.dp, vertical = 13.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(18.dp)
                        .border(
                            1.5.dp,
                            if (isSelected) Indigo else TextLow,
                            CircleShape
                        )
                        .padding(5.dp)
                        .background(
                            if (isSelected) Indigo else Color.Transparent,
                            CircleShape
                        )
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isSelected) TextHi else TextMid
                )
            }
        }
    }
}
