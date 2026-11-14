package ru.cyber102.arinspector.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.Formatters

@Composable
fun BrandTopBar(
    title: String,
    subtitle: String? = null,
    onBackClick: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    Surface(
        color = KstColors.NavyDark,
        contentColor = KstColors.White
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .heightIn(min = 60.dp)
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (onBackClick != null) {
                IconButton(
                    onClick = onBackClick,
                    modifier = Modifier.size(48.dp)
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = stringResource(R.string.cd_back),
                        tint = KstColors.White
                    )
                }
            } else {
                Spacer(modifier = Modifier.width(8.dp))
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 4.dp)
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    color = KstColors.White,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = KstColors.White.copy(alpha = 0.78f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                content = actions
            )
        }
    }
}

@Composable
fun EngineeringCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    contentPadding: PaddingValues = PaddingValues(16.dp),
    content: @Composable ColumnScope.() -> Unit
) {
    val border = BorderStroke(1.dp, KstColors.Border)
    if (onClick != null) {
        Surface(
            onClick = onClick,
            modifier = modifier,
            shape = PromScanShapesTokens.Card,
            color = KstColors.Surface,
            border = border,
            tonalElevation = 0.dp,
            shadowElevation = 0.dp
        ) {
            Column(
                modifier = Modifier.padding(contentPadding),
                content = content
            )
        }
    } else {
        Surface(
            modifier = modifier,
            shape = PromScanShapesTokens.Card,
            color = KstColors.Surface,
            border = border,
            tonalElevation = 0.dp,
            shadowElevation = 0.dp
        ) {
            Column(
                modifier = Modifier.padding(contentPadding),
                content = content
            )
        }
    }
}

@Composable
fun PrimaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    containerColor: Color = KstColors.Accent
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 48.dp),
        shape = PromScanShapesTokens.Control,
        colors = ButtonDefaults.buttonColors(
            containerColor = containerColor,
            contentColor = KstColors.White,
            disabledContainerColor = KstColors.Border,
            disabledContentColor = KstColors.TextSecondary
        )
    ) {
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
fun SecondaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 48.dp),
        shape = PromScanShapesTokens.Control,
        border = BorderStroke(1.dp, if (enabled) KstColors.Accent else KstColors.Border),
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = KstColors.Accent,
            disabledContentColor = KstColors.TextSecondary
        )
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
fun StatusPillBadge(
    label: String,
    fgColor: Color,
    bgColor: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(CircleShape)
            .background(bgColor)
            .border(1.dp, fgColor.copy(alpha = 0.25f), CircleShape)
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = fgColor,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1
        )
    }
}

@Composable
fun SeverityBadge(severity: String?, modifier: Modifier = Modifier) {
    val (fg, bg) = when (severity?.lowercase()) {
        "high" -> KstColors.Error to KstColors.ErrorTint
        "medium" -> KstColors.Warning to KstColors.WarningTint
        else -> KstColors.Warning to KstColors.WarningTint
    }
    val text = "${stringResource(R.string.criticality_label)}: ${Formatters.severityLabel(severity)}"
    StatusPillBadge(label = text, fgColor = fg, bgColor = bg, modifier = modifier)
}

@Composable
fun ReportStatusBadge(status: String?, modifier: Modifier = Modifier) {
    val (fg, bg) = when (status?.lowercase()) {
        "open" -> KstColors.Error to KstColors.ErrorTint
        "in_progress" -> KstColors.Accent to KstColors.AccentTint
        "closed" -> KstColors.Success to KstColors.SuccessTint
        else -> KstColors.TextSecondary to KstColors.Background
    }
    StatusPillBadge(
        label = Formatters.reportStatusLabel(status),
        fgColor = fg,
        bgColor = bg,
        modifier = modifier
    )
}

@Composable
fun EquipmentStateBadge(state: String?, modifier: Modifier = Modifier) {
    val (fg, bg) = when (state?.lowercase()) {
        "operational" -> KstColors.Success to KstColors.SuccessTint
        "maintenance" -> KstColors.Warning to KstColors.WarningTint
        "fault" -> KstColors.Error to KstColors.ErrorTint
        else -> KstColors.TextSecondary to KstColors.Background
    }
    StatusPillBadge(
        label = Formatters.equipmentStateLabel(state),
        fgColor = fg,
        bgColor = bg,
        modifier = modifier
    )
}

@Composable
fun ProbabilityBarRow(
    label: String,
    probability: Double?,
    modifier: Modifier = Modifier
) {
    val value = (probability ?: 0.0).toFloat().coerceIn(0f, 1f)
    val barColor = when {
        value >= 0.65f -> KstColors.Error
        value >= 0.3f -> KstColors.SeverityMedium
        else -> KstColors.Accent
    }
    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = KstColors.TextSecondary
            )
            Text(
                text = Formatters.percent(probability),
                style = MaterialTheme.typography.labelMedium,
                color = KstColors.TextPrimary,
                fontWeight = FontWeight.SemiBold
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { value },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(CircleShape),
            color = barColor,
            trackColor = KstColors.Border
        )
    }
}
