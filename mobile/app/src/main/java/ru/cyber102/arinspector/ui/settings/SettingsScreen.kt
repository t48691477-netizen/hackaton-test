package ru.cyber102.arinspector.ui.settings

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.BuildConfig
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.ui.components.BrandTopBar
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.SecondaryActionButton
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.Formatters

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
    onLoggedOut: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val healthOkText = stringResource(R.string.settings_health_ok)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        BrandTopBar(
            title = stringResource(R.string.settings_title),
            onBackClick = onBack
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // Адрес сервера и проверка GET health
            EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.settings_server_section),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = uiState.serverUrlInput,
                    onValueChange = viewModel::onServerUrlChanged,
                    label = { Text(stringResource(R.string.settings_server_url_label)) },
                    placeholder = { Text(stringResource(R.string.settings_server_url_hint)) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    shape = PromScanShapesTokens.Control,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = KstColors.Accent,
                        unfocusedBorderColor = KstColors.Border
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("server_url_input")
                )

                val health = uiState.healthStatus
                if (health != null) {
                    Spacer(modifier = Modifier.height(10.dp))
                    Surface(
                        color = if (health.isSuccess) KstColors.SuccessTint else KstColors.ErrorTint,
                        shape = PromScanShapesTokens.Control,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(
                                imageVector = if (health.isSuccess) Icons.Filled.CheckCircle else Icons.Filled.Warning,
                                contentDescription = null,
                                tint = if (health.isSuccess) KstColors.Success else KstColors.Error,
                                modifier = Modifier.size(18.dp)
                            )
                            Text(
                                text = health.message,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (health.isSuccess) KstColors.Success else KstColors.Error,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    SecondaryActionButton(
                        text = stringResource(R.string.settings_save_url),
                        onClick = { viewModel.saveServerUrl("Адрес сохранён") },
                        enabled = !uiState.isCheckingHealth,
                        modifier = Modifier
                            .weight(1f)
                            .testTag("save_server_url_button")
                    )
                    if (uiState.isCheckingHealth) {
                        Row(
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = KstColors.Accent,
                                strokeWidth = 2.5.dp
                            )
                        }
                    } else {
                        PrimaryActionButton(
                            text = stringResource(R.string.settings_check_health),
                            onClick = { viewModel.checkHealth(healthOkText) },
                            modifier = Modifier
                                .weight(1f)
                                .testTag("check_health_button")
                        )
                    }
                }
            }

            // Интервал анализа
            EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.settings_interval_section),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    val intervals = listOf(
                        1 to stringResource(R.string.settings_interval_1s),
                        2 to stringResource(R.string.settings_interval_2s),
                        3 to stringResource(R.string.settings_interval_3s)
                    )
                    intervals.forEach { (sec, label) ->
                        val selected = uiState.analysisIntervalSec == sec
                        FilterChip(
                            selected = selected,
                            onClick = { viewModel.selectInterval(sec) },
                            label = {
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.labelLarge
                                )
                            },
                            shape = CircleShape,
                            colors = FilterChipDefaults.filterChipColors(
                                containerColor = KstColors.Background,
                                labelColor = KstColors.TextSecondary,
                                selectedContainerColor = KstColors.Accent,
                                selectedLabelColor = KstColors.White
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled = true,
                                selected = selected,
                                borderColor = KstColors.Border,
                                selectedBorderColor = KstColors.Accent
                            ),
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 48.dp)
                                .testTag("interval_chip_$sec")
                        )
                    }
                }
            }

            // Профиль сотрудника (только при авторизованной сессии)
            val account = uiState.account
            if (account != null) {
                EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Person,
                            contentDescription = null,
                            tint = KstColors.Accent
                        )
                        Text(
                            text = stringResource(R.string.settings_profile_section),
                            style = MaterialTheme.typography.titleMedium,
                            color = KstColors.TextPrimary
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    ProfileRow("ФИО", account.fullName ?: "—")
                    ProfileRow("Роль", Formatters.roleLabel(account.role))
                    ProfileRow("E-mail", account.email ?: "—")

                    Spacer(modifier = Modifier.height(14.dp))
                    HorizontalDivider(color = KstColors.Border)
                    Spacer(modifier = Modifier.height(14.dp))

                    Button(
                        onClick = { viewModel.logout(onLoggedOut) },
                        enabled = !uiState.isLoggingOut,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp)
                            .testTag("logout_button"),
                        shape = PromScanShapesTokens.Control,
                        border = BorderStroke(1.dp, KstColors.Error),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = KstColors.ErrorTint,
                            contentColor = KstColors.Error
                        )
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = stringResource(R.string.settings_logout),
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            // Версия приложения
            EngineeringCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = stringResource(R.string.settings_version_section),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                ProfileRow(
                    label = stringResource(R.string.settings_version_label),
                    value = BuildConfig.VERSION_NAME
                )
            }
        }
    }
}

@Composable
private fun ProfileRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = KstColors.TextSecondary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = KstColors.TextPrimary,
            fontWeight = FontWeight.Medium
        )
    }
}
