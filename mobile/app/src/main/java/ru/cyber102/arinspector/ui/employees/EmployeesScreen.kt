package ru.cyber102.arinspector.ui.employees

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.data.model.EmployeeDto
import ru.cyber102.arinspector.ui.components.BrandTopBar
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.theme.KstColors

private val ROLE_LABELS = linkedMapOf(
    "engineer" to "Рабочий",
    "dispatcher" to "Диспетчер",
    "admin" to "Администратор"
)

@Composable
fun EmployeesScreen(
    viewModel: EmployeesViewModel,
    isDirector: Boolean
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var fullName by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var role by remember { mutableStateOf("engineer") }
    var deleteTarget by remember { mutableStateOf<EmployeeDto?>(null) }

    val roles = ROLE_LABELS.filterKeys { isDirector || it != "admin" }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        BrandTopBar(title = "Сотрудники", subtitle = "Управление доступом")

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить сотрудника", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = fullName,
                        onValueChange = { fullName = it },
                        label = { Text("ФИО") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Email") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        roles.forEach { (key, label) ->
                            FilterChip(
                                selected = role == key,
                                onClick = { role = key },
                                label = { Text(label) }
                            )
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    PrimaryActionButton(
                        text = "Добавить",
                        enabled = fullName.trim().length >= 2 && email.contains("@"),
                        onClick = {
                            viewModel.create(fullName, email, role)
                            fullName = ""
                            email = ""
                        },
                        modifier = Modifier.fillMaxWidth()
                    )
                    state.errorMessage?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = KstColors.Error, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }

            items(state.employees, key = { it.id }) { employee ->
                val canDelete = isDirector || employee.role != "admin"
                EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(employee.fullName, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "${ROLE_LABELS[employee.role] ?: employee.role} · ${employee.email}",
                                style = MaterialTheme.typography.bodySmall,
                                color = KstColors.TextSecondary
                            )
                        }
                        TextButton(
                            enabled = canDelete,
                            onClick = { deleteTarget = employee }
                        ) {
                            Text(
                                "Удалить",
                                color = if (canDelete) KstColors.Error else KstColors.TextSecondary
                            )
                        }
                    }
                }
            }
        }
    }

    deleteTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить сотрудника?") },
            text = { Text("${target.fullName} потеряет доступ, его ключ перестанет работать.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.delete(target.id)
                    deleteTarget = null
                }) { Text("Удалить") }
            },
            dismissButton = {
                TextButton(onClick = { deleteTarget = null }) { Text("Отмена") }
            }
        )
    }

    state.issuedKey?.let { key ->
        val clipboardManager = androidx.compose.ui.platform.LocalClipboardManager.current
        AlertDialog(
            onDismissRequest = { viewModel.dismissKey() },
            title = { Text("Ключ доступа") },
            text = {
                Text("${state.issuedFor}: $key\n\nКлюч показывается один раз, передайте его сотруднику.")
            },
            confirmButton = {
                TextButton(onClick = {
                    clipboardManager.setText(androidx.compose.ui.text.AnnotatedString(key))
                    viewModel.dismissKey()
                }) { Text("Скопировать и закрыть") }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissKey() }) { Text("Закрыть") }
            }
        )
    }
}
