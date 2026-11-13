package ru.cyber102.arinspector.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudGreen
import ru.cyber102.arinspector.ui.theme.HudLine
import ru.cyber102.arinspector.ui.theme.SafetyYellow
import ru.cyber102.arinspector.ui.theme.TextDim

/**
 * Главная кнопка в луче большого пальца (правая рука).
 *
 * Одна цель на весь низ экрана: 76 dp круг с подписью-«шильдиком» внутри.
 * Кнопка позиционируется в правом нижнем углу, вторая (ассистент) — чуть выше
 * и левее, чтобы расстояние между мишенями было больше 16 dp.
 */
@Composable
fun ThumbAction(
    label: String,
    caption: String,
    accent: Color,
    modifier: Modifier = Modifier,
    size: Dp = 76.dp,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(size)
                .clip(CircleShape)
                .background(if (enabled) accent else HudLine)
                .border(2.dp, HudBlack.copy(alpha = 0.55f), CircleShape)
                .clickable(enabled = enabled, onClick = onClick),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Black,
                    fontSize = 12.sp,
                    color = HudBlack,
                    textAlign = TextAlign.Center,
                    maxLines = 2
                )
                Text(
                    text = caption.uppercase(),
                    fontSize = 7.5.sp,
                    letterSpacing = 0.6.sp,
                    color = HudBlack.copy(alpha = 0.72f),
                    textAlign = TextAlign.Center,
                    maxLines = 1
                )
            }
        }
    }
}

/** Вторичная круглая кнопка — ассистент, настройки. Не конкурирует с главной. */
@Composable
fun ThumbSecondary(
    modifier: Modifier = Modifier,
    size: Dp = 52.dp,
    onClick: () -> Unit,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(HudBlack.copy(alpha = 0.88f))
            .border(1.2.dp, HudLine, CircleShape)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        content()
    }
}

/** Статус-маркер: форма + текст, читается и в монохроме, и на солнце. */
@Composable
fun StatusBadge(
    label: String,
    accent: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(CircleShape)
            .background(HudBlack.copy(alpha = 0.9f))
            .border(1.2.dp, accent, CircleShape)
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            text = label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = accent
        )
    }
}

@Composable
fun DimCaption(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall,
        color = TextDim
    )
}
