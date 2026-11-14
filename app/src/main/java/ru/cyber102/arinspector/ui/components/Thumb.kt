package ru.cyber102.arinspector.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.cyber102.arinspector.ui.theme.Aqua
import ru.cyber102.arinspector.ui.theme.Hairline
import ru.cyber102.arinspector.ui.theme.HairlineStrong
import ru.cyber102.arinspector.ui.theme.Indigo
import ru.cyber102.arinspector.ui.theme.IndigoDeep
import ru.cyber102.arinspector.ui.theme.IndigoSoft
import ru.cyber102.arinspector.ui.theme.Ink
import ru.cyber102.arinspector.ui.theme.InkHover
import ru.cyber102.arinspector.ui.theme.TextHi
import ru.cyber102.arinspector.ui.theme.TextLow

/**
 * Главная кнопка в луче большого пальца (правая рука).
 *
 * Круглая цель 78 dp с индиго-градиентом, мягкой тенью-ореолом и подписью
 * внутри. Расставлена так, чтобы от системного жеста внизу было не меньше
 * 20 dp — не задевается при свайпе «назад».
 */
@Composable
fun ThumbAction(
    label: String,
    caption: String,
    accent: Color = Indigo,
    modifier: Modifier = Modifier,
    size: Dp = 78.dp,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .size(size + 10.dp),
        contentAlignment = Alignment.Center
    ) {
        // Ореол: чуть расфокусированная подложка того же цвета.
        Box(
            Modifier
                .size(size + 10.dp)
                .background(
                    Brush.radialGradient(
                        listOf(accent.copy(alpha = if (enabled) 0.28f else 0.06f), Color.Transparent)
                    ),
                    CircleShape
                )
        )
        Column(
            modifier = Modifier
                .size(size)
                .clip(CircleShape)
                .background(
                    if (enabled) {
                        Brush.linearGradient(listOf(IndigoSoft, accent, IndigoDeep))
                    } else {
                        Brush.linearGradient(listOf(HairlineStrong, Hairline))
                    }
                )
                .clickable(enabled = enabled, onClick = onClick),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp,
                color = TextHi,
                textAlign = TextAlign.Center,
                maxLines = 2
            )
            Text(
                text = caption.uppercase(),
                fontSize = 8.sp,
                letterSpacing = 0.7.sp,
                color = TextHi.copy(alpha = 0.7f),
                textAlign = TextAlign.Center,
                maxLines = 1
            )
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
            .background(InkHover)
            .border(1.dp, HairlineStrong, CircleShape)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        content()
    }
}

/** Статус-маркер: форма + текст. Читается в монохроме и на ярком солнце. */
@Composable
fun StatusBadge(
    label: String,
    accent: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(999.dp))
            .background(Ink.copy(alpha = 0.86f))
            .border(1.dp, accent.copy(alpha = 0.7f), RoundedCornerShape(999.dp))
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
        color = TextLow
    )
}

/** Утилита для бейджа «живого» режима. */
val LiveAccent: Color = Aqua

