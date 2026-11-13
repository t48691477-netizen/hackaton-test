package ru.cyber102.arinspector.ui.result

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.data.EquipmentComponent
import ru.cyber102.arinspector.data.InspectResponse
import ru.cyber102.arinspector.data.ResolutionStatus
import ru.cyber102.arinspector.ui.components.ConfidenceBar
import ru.cyber102.arinspector.ui.components.HudDivider
import ru.cyber102.arinspector.ui.components.HudPanel
import ru.cyber102.arinspector.ui.components.KeyValueRow
import ru.cyber102.arinspector.ui.components.MonoLabel
import ru.cyber102.arinspector.ui.components.PrimaryAction
import ru.cyber102.arinspector.ui.components.SectionTitle
import ru.cyber102.arinspector.ui.components.SegmentedChoice
import ru.cyber102.arinspector.ui.components.StatusPill
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudGreen
import ru.cyber102.arinspector.ui.theme.HudLine
import ru.cyber102.arinspector.ui.theme.HudSurface
import ru.cyber102.arinspector.ui.theme.HudRed
import ru.cyber102.arinspector.ui.theme.SafetyYellow
import ru.cyber102.arinspector.ui.theme.TextMuted
import ru.cyber102.arinspector.ui.theme.TextPrimary
import ru.cyber102.arinspector.util.PdfAct
import ru.cyber102.arinspector.vm.InspectionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultSheet(
    equipment: Equipment,
    component: EquipmentComponent,
    defect: Defect?,
    inspection: InspectResponse?,
    vm: InspectionViewModel,
    onDismiss: () -> Unit
) {
    val report by vm.report.collectAsStateWithLifecycle()
    val reporting by vm.reporting.collectAsStateWithLifecycle()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val context = LocalContext.current

    var status by remember(component.id, defect?.id) { mutableStateOf<ResolutionStatus?>(null) }
    var comment by remember(component.id, defect?.id) { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = {
            vm.clearReport()
            onDismiss()
        },
        sheetState = sheetState,
        containerColor = HudSurface,
        contentColor = TextPrimary,
        dragHandle = {
            Box(
                Modifier
                    .padding(vertical = 10.dp)
                    .size(width = 44.dp, height = 4.dp)
                    .background(HudLine, RoundedCornerShape(2.dp))
            )
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                MonoLabel("УЗЕЛ ${component.id}")
                Spacer(Modifier.width(10.dp))
                StatusPill(
                    text = when {
                        defect == null -> "ЧИСТО"
                        defect.isCritical -> "CRITICAL"
                        else -> "WARNING"
                    },
                    color = when {
                        defect == null -> HudGreen
                        defect.isCritical -> HudRed
                        else -> SafetyYellow
                    }
                )
                Spacer(Modifier.weight(1f))
                IconButton(onClick = {
                    vm.clearReport()
                    onDismiss()
                }) {
                    Icon(Icons.Filled.Close, contentDescription = "Закрыть", tint = TextMuted)
                }
            }

            Text(
                text = component.name,
                style = MaterialTheme.typography.headlineMedium,
                color = TextPrimary
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = equipment.name,
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted
            )

            Spacer(Modifier.height(14.dp))
            HudPanel(Modifier.fillMaxWidth(), accent = HudLine) {
                Column {
                    KeyValueRow(
                        "Смещение от QR",
                        "x=%.2f  y=%.2f  z=%.2f м".format(
                            component.offsetFromQr.x,
                            component.offsetFromQr.y,
                            component.offsetFromQr.z
                        )
                    )
                    Spacer(Modifier.height(6.dp))
                    KeyValueRow("Радиус зоны", "%.2f м".format(component.radius))
                }
            }

            Spacer(Modifier.height(20.dp))
            SectionTitle("01", if (defect == null) "Результат осмотра" else "Обнаруженный дефект")

            if (defect != null) {
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Filled.WarningAmber,
                        contentDescription = null,
                        tint = if (defect.isCritical) HudRed else SafetyYellow,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = defect.displayTitle,
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        text = "${(defect.confidence * 100).toInt()}%",
                        style = MaterialTheme.typography.labelMedium,
                        color = if (defect.isCritical) HudRed else SafetyYellow
                    )
                }
                Spacer(Modifier.height(8.dp))
                ConfidenceBar(
                    value = defect.confidence,
                    color = if (defect.isCritical) HudRed else SafetyYellow
                )
                Spacer(Modifier.height(8.dp))
                MonoLabel("уверенность модели · ${defect.type.uppercase()}")

                if (defect.analysis != null) {
                    Spacer(Modifier.height(14.dp))
                    HudPanel(Modifier.fillMaxWidth(), accent = SafetyYellow) {
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    text = "ИНЖЕНЕРНЫЙ АНАЛИЗ",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = SafetyYellow
                                )
                                Spacer(Modifier.weight(1f))
                                MonoLabel("LLM")
                            }
                            Spacer(Modifier.height(8.dp))
                            Text(
                                text = defect.analysis,
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary
                            )
                        }
                    }
                }

                if (defect.recommendation != null) {
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = "РЕКОМЕНДАЦИЯ",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = defect.recommendation,
                        style = MaterialTheme.typography.bodyMedium,
                        color = HudGreen
                    )
                }
            } else {
                Spacer(Modifier.height(12.dp))
                HudPanel(Modifier.fillMaxWidth(), accent = HudGreen) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                Icons.Filled.CheckCircle,
                                contentDescription = null,
                                tint = HudGreen,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "Дефектов в зоне узла не обнаружено",
                                style = MaterialTheme.typography.titleMedium,
                                color = TextPrimary
                            )
                        }
                        inspection?.analysis?.let {
                            Spacer(Modifier.height(10.dp))
                            Text(
                                text = it,
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextMuted
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(22.dp))

            if (report == null) {
                SectionTitle("02", "Решение инженера")
                Spacer(Modifier.height(12.dp))
                SegmentedChoice(
                    options = ResolutionStatus.entries.map { it to it.label },
                    selected = status,
                    modifier = Modifier.fillMaxWidth(),
                    onSelect = { status = it }
                )

                Spacer(Modifier.height(14.dp))
                OutlinedTextField(
                    value = comment,
                    onValueChange = { comment = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = {
                        Text(
                            "Комментарий к акту (необязательно)",
                            color = TextMuted,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    },
                    minLines = 2,
                    textStyle = MaterialTheme.typography.bodyMedium.copy(
                        fontFamily = FontFamily.Monospace,
                        color = TextPrimary
                    ),
                    shape = RoundedCornerShape(8.dp)
                )

                Spacer(Modifier.height(16.dp))
                PrimaryAction(
                    text = if (reporting) "Отправляем акт…" else "Зафиксировать акт",
                    icon = Icons.Filled.AssignmentTurnedIn,
                    enabled = status != null && !reporting,
                    onClick = {
                        status?.let {
                            vm.submitReport(
                                equipmentId = equipment.id,
                                componentId = component.id,
                                defect = defect,
                                status = it,
                                comment = comment
                            )
                        }
                    }
                )
                if (status == null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Выберите статус, чтобы сформировать акт",
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted
                    )
                }
                if (reporting) {
                    Spacer(Modifier.height(12.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(14.dp),
                            color = SafetyYellow,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        MonoLabel("POST /api/reports")
                    }
                }
            } else {
                HudPanel(Modifier.fillMaxWidth(), accent = HudGreen) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                Icons.Filled.CheckCircle,
                                contentDescription = null,
                                tint = HudGreen,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(Modifier.width(10.dp))
                            Column {
                                Text(
                                    text = "Акт зафиксирован",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = TextPrimary
                                )
                                MonoLabel("№ ${report!!.reportId}")
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                        HudDivider()
                        Spacer(Modifier.height(12.dp))
                        Text(
                            text = "Решение: ${status?.label ?: "—"}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextMuted
                        )
                        Spacer(Modifier.height(14.dp))
                        PrimaryAction(
                            text = "Скачать акт (PDF)",
                            icon = Icons.Filled.PictureAsPdf,
                            onClick = {
                                val file = PdfAct.build(
                                    context = context,
                                    equipment = equipment,
                                    component = component,
                                    defect = defect,
                                    status = status ?: ResolutionStatus.FIXED,
                                    comment = comment,
                                    reportId = report!!.reportId
                                )
                                PdfAct.share(context, file)
                            }
                        )
                        Spacer(Modifier.height(6.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center
                        ) {
                            TextButton(onClick = {
                                vm.clearReport()
                                onDismiss()
                            }) {
                                Text("Готово", color = Color(0xFF8FA3AC))
                            }
                        }
                    }
                }
            }
        }
    }
}
