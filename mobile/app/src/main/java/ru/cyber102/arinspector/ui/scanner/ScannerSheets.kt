package ru.cyber102.arinspector.ui.scanner

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.data.model.DetailedInspectResponse
import ru.cyber102.arinspector.data.model.EquipmentDto
import ru.cyber102.arinspector.ui.components.EquipmentStateBadge
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.SecondaryActionButton
import ru.cyber102.arinspector.ui.components.SeverityBadge
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.Formatters

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EquipmentPassportSheet(
    equipment: EquipmentDto,
    onDismiss: () -> Unit,
    onStartAnalysis: () -> Unit,
    onChangeEquipment: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = KstColors.Surface
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.scanner_passport_title),
                    style = MaterialTheme.typography.labelLarge,
                    color = KstColors.Accent
                )
                EquipmentStateBadge(state = equipment.state)
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = equipment.name ?: equipment.id ?: "—",
                style = MaterialTheme.typography.headlineMedium,
                color = KstColors.TextPrimary
            )

            Spacer(modifier = Modifier.height(12.dp))

            PassportInfoGrid(equipment = equipment)

            val specs = equipment.specs.orEmpty()
            if (specs.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(R.string.eq_specs_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))
                specs.forEach { spec ->
                    val valWithUnit = listOfNotNull(
                        spec.value?.takeIf { it.isNotBlank() },
                        spec.unit?.takeIf { it.isNotBlank() }
                    ).joinToString(" ")
                    PassportKeyValueRow(
                        label = spec.label ?: "—",
                        value = valWithUnit.ifBlank { "—" }
                    )
                }
            }

            val nodes = equipment.nodes.orEmpty()
            if (nodes.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(R.string.eq_nodes_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))
                nodes.forEach { node ->
                    Surface(
                        shape = PromScanShapesTokens.Control,
                        color = KstColors.Background,
                        border = BorderStroke(1.dp, KstColors.Border),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(
                                text = node.name ?: node.id ?: "Узел",
                                style = MaterialTheme.typography.titleSmall,
                                color = KstColors.TextPrimary
                            )
                            node.specs.orEmpty().forEach { spec ->
                                val valWithUnit = listOfNotNull(
                                    spec.value?.takeIf { it.isNotBlank() },
                                    spec.unit?.takeIf { it.isNotBlank() }
                                ).joinToString(" ")
                                Text(
                                    text = "${spec.label ?: "—"}: ${valWithUnit.ifBlank { "—" }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = KstColors.TextSecondary
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                SecondaryActionButton(
                    text = stringResource(R.string.scanner_change_equipment),
                    onClick = onChangeEquipment,
                    modifier = Modifier
                        .weight(1f)
                        .testTag("passport_change_equipment_button")
                )
                PrimaryActionButton(
                    text = stringResource(R.string.scanner_analyze_start),
                    onClick = onStartAnalysis,
                    modifier = Modifier
                        .weight(1.3f)
                        .testTag("passport_start_analysis_button")
                )
            }
        }
    }
}

@Composable
private fun PassportInfoGrid(equipment: EquipmentDto) {
    Surface(
        shape = PromScanShapesTokens.Control,
        color = KstColors.Background,
        border = BorderStroke(1.dp, KstColors.Border),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            PassportKeyValueRow("ID", equipment.id ?: "—")
            PassportKeyValueRow(stringResource(R.string.eq_inventory_number), equipment.inventoryNumber ?: "—")
            PassportKeyValueRow(stringResource(R.string.eq_location), equipment.location ?: "—")
            PassportKeyValueRow(
                stringResource(R.string.eq_last_to),
                Formatters.formatDateShort(equipment.lastMaintenanceAt)
            )
            PassportKeyValueRow(
                stringResource(R.string.eq_next_to),
                Formatters.formatDateShort(equipment.nextMaintenanceAt)
            )
        }
    }
}

@Composable
private fun PassportKeyValueRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = KstColors.TextSecondary,
            modifier = Modifier.weight(1f)
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            color = KstColors.TextPrimary,
            fontWeight = FontWeight.Medium
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailedInspectionSheet(
    detail: DetailedInspectResponse,
    onDismiss: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = KstColors.Surface
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
        ) {
            Text(
                text = stringResource(R.string.scanner_detailed_title),
                style = MaterialTheme.typography.headlineMedium,
                color = KstColors.TextPrimary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = detail.summary.orEmpty().ifBlank { "—" },
                style = MaterialTheme.typography.bodyMedium,
                color = KstColors.TextSecondary
            )

            val findings = detail.findings.orEmpty()
            if (findings.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(R.string.scanner_detailed_findings),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))
                findings.forEach { finding ->
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
                                    text = finding.title ?: "Дефект",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = KstColors.TextPrimary,
                                    modifier = Modifier.weight(1f)
                                )
                                SeverityBadge(severity = finding.severity)
                            }
                            if (!finding.description.isNullOrBlank()) {
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = finding.description,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = KstColors.TextSecondary
                                )
                            }
                            if (!finding.recommendation.isNullOrBlank()) {
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = finding.recommendation,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = KstColors.Accent,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    }
                }
            }

            val causes = detail.probableCauses.orEmpty()
            if (causes.isNotEmpty()) {
                Spacer(modifier = Modifier.height(14.dp))
                HorizontalDivider(color = KstColors.Border)
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = stringResource(R.string.scanner_detailed_causes),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                causes.forEach { cause ->
                    Text(
                        text = "• $cause",
                        style = MaterialTheme.typography.bodyMedium,
                        color = KstColors.TextPrimary,
                        modifier = Modifier.padding(vertical = 2.dp)
                    )
                }
            }

            val steps = detail.recommendationSteps.orEmpty()
            if (steps.isNotEmpty()) {
                Spacer(modifier = Modifier.height(14.dp))
                HorizontalDivider(color = KstColors.Border)
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = stringResource(R.string.scanner_detailed_steps),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                steps.forEachIndexed { idx, step ->
                    Text(
                        text = "${idx + 1}. $step",
                        style = MaterialTheme.typography.bodyMedium,
                        color = KstColors.TextPrimary,
                        modifier = Modifier.padding(vertical = 3.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(18.dp))
            PrimaryActionButton(
                text = stringResource(R.string.close),
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
fun ManualEquipmentIdDialog(
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var inputId by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = KstColors.Surface,
        shape = PromScanShapesTokens.Card,
        title = {
            Text(
                text = stringResource(R.string.scanner_manual_id_title),
                style = MaterialTheme.typography.titleLarge,
                color = KstColors.TextPrimary
            )
        },
        text = {
            OutlinedTextField(
                value = inputId,
                onValueChange = { inputId = it },
                label = { Text(stringResource(R.string.scanner_manual_id_label)) },
                singleLine = true,
                shape = PromScanShapesTokens.Control,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = KstColors.Accent,
                    unfocusedBorderColor = KstColors.Border
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("manual_equipment_id_input")
            )
        },
        confirmButton = {
            PrimaryActionButton(
                text = stringResource(R.string.scanner_manual_id_confirm),
                onClick = { onConfirm(inputId.trim()) },
                enabled = inputId.isNotBlank(),
                modifier = Modifier.testTag("manual_equipment_id_confirm_button")
            )
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                modifier = Modifier.heightIn(min = 48.dp)
            ) {
                Text(stringResource(R.string.cancel), color = KstColors.TextSecondary)
            }
        }
    )
}

@Composable
fun CreateReportDialog(
    isSubmitting: Boolean,
    onDismiss: () -> Unit,
    onSubmit: (String) -> Unit
) {
    var comment by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!isSubmitting) onDismiss() },
        containerColor = KstColors.Surface,
        shape = PromScanShapesTokens.Card,
        title = {
            Text(
                text = stringResource(R.string.scanner_create_report_title),
                style = MaterialTheme.typography.titleLarge,
                color = KstColors.TextPrimary
            )
        },
        text = {
            OutlinedTextField(
                value = comment,
                onValueChange = { comment = it },
                label = { Text(stringResource(R.string.scanner_create_report_comment)) },
                placeholder = { Text(stringResource(R.string.scanner_create_report_hint)) },
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
                    .testTag("create_report_comment_input")
            )
        },
        confirmButton = {
            if (isSubmitting) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .padding(12.dp)
                        .size(24.dp),
                    color = KstColors.Accent,
                    strokeWidth = 2.5.dp
                )
            } else {
                PrimaryActionButton(
                    text = stringResource(R.string.scanner_create_report_submit),
                    onClick = { onSubmit(comment) },
                    modifier = Modifier.testTag("create_report_submit_button")
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
