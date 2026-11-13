package ru.cyber102.arinspector.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.ui.components.HudPanel
import ru.cyber102.arinspector.ui.components.PrimaryAction
import ru.cyber102.arinspector.ui.components.SectionTitle
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudLine
import ru.cyber102.arinspector.ui.theme.HudSurface
import ru.cyber102.arinspector.ui.theme.SafetyYellow
import ru.cyber102.arinspector.ui.theme.TextMuted
import ru.cyber102.arinspector.ui.theme.TextPrimary
import ru.cyber102.arinspector.vm.InspectionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsSheet(vm: InspectionViewModel, onDismiss: () -> Unit) {
    val demoMode by vm.demoMode.collectAsStateWithLifecycle()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    var demo by remember { mutableStateOf(demoMode) }
    var url by remember { mutableStateOf(vm.settings.baseUrl) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = HudSurface,
        contentColor = TextPrimary
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
        ) {
            SectionTitle("01", "Подключение к API")
            Spacer(Modifier.height(14.dp))

            HudPanel(modifier = Modifier.fillMaxWidth(), accent = SafetyYellow) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Демо-режим", color = TextPrimary)
                            Text(
                                "Ответы API генерируются локально. Питч не зависит от сети.",
                                color = TextMuted,
                                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium
                            )
                        }
                        Spacer(Modifier.width(12.dp))
                        Switch(
                            checked = demo,
                            onCheckedChange = { demo = it },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = HudBlack,
                                checkedTrackColor = SafetyYellow,
                                uncheckedThumbColor = TextMuted,
                                uncheckedTrackColor = HudLine
                            )
                        )
                    }
                }
            }

            Spacer(Modifier.height(14.dp))

            Text(
                "Базовый URL",
                color = TextMuted,
                style = androidx.compose.material3.MaterialTheme.typography.labelMedium
            )
            Spacer(Modifier.height(6.dp))
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                enabled = !demo,
                placeholder = { Text("http://192.168.1.10:8080/") },
                textStyle = androidx.compose.material3.MaterialTheme.typography.bodyMedium.copy(
                    fontFamily = FontFamily.Monospace,
                    color = TextPrimary
                ),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                shape = RoundedCornerShape(8.dp)
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Для телефона укажите IP компьютера с мок-сервером из папки backend/. " +
                    "Эмулятор видит хост как 10.0.2.2.",
                color = TextMuted,
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium
            )

            Spacer(Modifier.height(18.dp))

            PrimaryAction(
                text = "Применить",
                onClick = {
                    vm.setDemoMode(demo)
                    if (url.isNotBlank()) vm.setBaseUrl(url)
                    onDismiss()
                }
            )
        }
    }
}
