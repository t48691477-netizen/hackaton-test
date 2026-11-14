package ru.cyber102.arinspector.ui.tasks

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.ImageLoader
import coil.compose.AsyncImage
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.data.model.ReportDto
import ru.cyber102.arinspector.ui.components.BrandTopBar
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.ReportStatusBadge
import ru.cyber102.arinspector.ui.components.SeverityBadge
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.Formatters

@Composable
fun TaskDetailScreen(
    viewModel: TaskDetailViewModel,
    imageLoader: ImageLoader,
    onBack: () -> Unit,
    onShowMessage: (String) -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.snackbarMessage) {
        val msg = uiState.snackbarMessage
        if (!msg.isNullOrBlank()) {
            onShowMessage(msg)
            viewModel.consumeSnackbar()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        BrandTopBar(
            title = stringResource(R.string.task_detail_title),
            subtitle = uiState.report?.id,
            onBackClick = onBack
        )

        when {
            uiState.isLoading && uiState.report == null -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = KstColors.Accent)
                }
            }
            uiState.errorMessage != null && uiState.report == null -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = uiState.errorMessage.orEmpty(),
                            style = MaterialTheme.typography.bodyMedium,
                            color = KstColors.TextPrimary
                        )
                        Spacer(modifier = Modifier.height(14.dp))
                        PrimaryActionButton(
                            text = stringResource(R.string.tasks_retry),
                            onClick = viewModel::loadDetail,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
            uiState.report != null -> {
                val report = uiState.report!!
                TaskDetailBody(
                    report = report,
                    photoUrl = viewModel.resolvePhotoUrl(report.photoUrl),
                    imageLoader = imageLoader,
                    isUpdatingStatus = uiState.isUpdatingStatus,
                    onTakeInWork = viewModel::takeInWork,
                    onCompleteClick = { viewModel.setShowCompleteDialog(true) }
                )
            }
        }
    }

    if (uiState.showCompleteDialog) {
        CompleteTaskDialog(
            isSubmitting = uiState.isUpdatingStatus,
            onDismiss = { viewModel.setShowCompleteDialog(false) },
            onConfirm = viewModel::completeTask
        )
    }
}

@Composable
private fun TaskDetailBody(
    report: ReportDto,
    photoUrl: String?,
    imageLoader: ImageLoader,
    isUpdatingStatus: Boolean,
    onTakeInWork: () -> Unit,
    onCompleteClick: () -> Unit
) {
    val equipmentName = report.result?.equipment?.name
        ?: report.equipmentId
        ?: "Оборудование"
    val criticality = report.result?.llm?.criticality
        ?: report.result?.defects?.firstOrNull()?.severity
        ?: "low"

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .navigationBarsPadding()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        EngineeringCard(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                ReportStatusBadge(status = report.status)
                SeverityBadge(severity = criticality)
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = equipmentName,
                style = MaterialTheme.typography.headlineMedium,
                color = KstColors.TextPrimary
            )
            if (!report.result?.equipment?.location.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = report.result?.equipment?.location.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextSecondary
                )
            }

            if (!photoUrl.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(12.dp))
                AsyncImage(
                    model = photoUrl,
                    imageLoader = imageLoader,
                    contentDescription = equipmentName,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(210.dp)
                        .clip(PromScanShapesTokens.Control)
                        .border(1.dp, KstColors.Border, PromScanShapesTokens.Control)
                )
            }

            if (!report.comment.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = stringResource(R.string.task_comment_section),
                    style = MaterialTheme.typography.labelMedium,
                    color = KstColors.TextSecondary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = report.comment,
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextPrimary
                )
            }
        }

        // Исполнитель и хронология
        EngineeringCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.task_timeline),
                style = MaterialTheme.typography.titleMedium,
                color = KstColors.TextPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            KeyValueDetailRow(
                label = stringResource(R.string.task_assignee),
                value = report.assignee?.fullName?.takeIf { it.isNotBlank() }
                    ?: report.assignee?.id?.takeIf { it.isNotBlank() }
                    ?: stringResource(R.string.task_unassigned)
            )
            KeyValueDetailRow(
                label = stringResource(R.string.task_created_at),
                value = Formatters.formatDateTime(report.createdAt)
            )
            if (!report.startedAt.isNullOrBlank()) {
                KeyValueDetailRow(
                    label = stringResource(R.string.task_started_at),
                    value = Formatters.formatDateTime(report.startedAt)
                )
            }
            if (!report.completedAt.isNullOrBlank()) {
                KeyValueDetailRow(
                    label = stringResource(R.string.task_completed_at),
                    value = Formatters.formatDateTime(report.completedAt)
                )
            }
            if (!report.repairComment.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                HorizontalDivider(color = KstColors.Border)
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = stringResource(R.string.task_repair_comment_section),
                    style = MaterialTheme.typography.labelMedium,
                    color = KstColors.TextSecondary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = report.repairComment,
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextPrimary
                )
            }
        }

        // Дефекты
        val defects = report.result?.defects.orEmpty()
        if (defects.isNotEmpty()) {
            EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.task_defects),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))
                defects.forEach { defect ->
                    Surface(
                        shape = PromScanShapesTokens.Control,
                        color = KstColors.Background,
                        border = BorderStroke(1.dp, KstColors.Border),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "${defect.label ?: "Дефект"} (${Formatters.percent(defect.confidence)})",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = KstColors.TextPrimary,
                                    modifier = Modifier.weight(1f)
                                )
                                SeverityBadge(severity = defect.severity)
                            }
                            if (!defect.recommendation.isNullOrBlank()) {
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = defect.recommendation,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = KstColors.TextSecondary
                                )
                            }
                        }
                    }
                }
            }
        }

        // Заключение и рекомендации
        val summary = report.result?.summary
        val probableCause = report.result?.llm?.probableCause
        val steps = report.result?.llm?.recommendationSteps.orEmpty()
        if (!summary.isNullOrBlank() || !probableCause.isNullOrBlank() || steps.isNotEmpty()) {
            EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.task_conclusion),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                if (!summary.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = summary,
                        style = MaterialTheme.typography.bodyMedium,
                        color = KstColors.TextPrimary
                    )
                }
                if (!probableCause.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = probableCause,
                        style = MaterialTheme.typography.bodySmall,
                        color = KstColors.TextSecondary
                    )
                }
                if (steps.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = stringResource(R.string.task_recommendations),
                        style = MaterialTheme.typography.titleSmall,
                        color = KstColors.TextPrimary
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    steps.forEachIndexed { idx, step ->
                        Text(
                            text = "${idx + 1}. $step",
                            style = MaterialTheme.typography.bodyMedium,
                            color = KstColors.TextPrimary,
                            modifier = Modifier.padding(vertical = 2.dp)
                        )
                    }
                }
            }
        }

        // Кнопки перехода статуса
        when (report.status?.lowercase()) {
            "open" -> {
                PrimaryActionButton(
                    text = stringResource(R.string.task_take_in_work),
                    onClick = onTakeInWork,
                    enabled = !isUpdatingStatus,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp)
                        .testTag("take_in_work_button")
                )
            }
            "in_progress" -> {
                PrimaryActionButton(
                    text = stringResource(R.string.task_complete),
                    onClick = onCompleteClick,
                    enabled = !isUpdatingStatus,
                    containerColor = KstColors.Success,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp)
                        .testTag("complete_task_button")
                )
            }
        }
    }
}

@Composable
private fun KeyValueDetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = KstColors.TextSecondary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            color = KstColors.TextPrimary,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun CompleteTaskDialog(
    isSubmitting: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var comment by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!isSubmitting) onDismiss() },
        containerColor = KstColors.Surface,
        shape = PromScanShapesTokens.Card,
        title = {
            Text(
                text = stringResource(R.string.task_complete_dialog_title),
                style = MaterialTheme.typography.titleLarge,
                color = KstColors.TextPrimary
            )
        },
        text = {
            OutlinedTextField(
                value = comment,
                onValueChange = { comment = it },
                label = { Text(stringResource(R.string.task_repair_comment_label)) },
                placeholder = { Text(stringResource(R.string.task_repair_comment_hint)) },
                minLines = 3,
                maxLines = 5,
                enabled = !isSubmitting,
                shape = PromScanShapesTokens.Control,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = KstColors.Accent,
                    unfocusedBorderColor = KstColors.Border
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("repair_comment_input")
            )
        },
        confirmButton = {
            if (isSubmitting) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .padding(12.dp)
                        .size(24.dp),
                    color = KstColors.Success,
                    strokeWidth = 2.5.dp
                )
            } else {
                PrimaryActionButton(
                    text = stringResource(R.string.task_confirm_complete),
                    onClick = { onConfirm(comment) },
                    containerColor = KstColors.Success,
                    modifier = Modifier.testTag("confirm_complete_task_button")
                )
            }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                enabled = !isSubmitting,
                modifier = Modifier.heightIn(min = 48.dp)
            ) {
                Text(stringResource(R.string.cancel), color = KstColors.TextSecondary)
            }
        }
    )
}
