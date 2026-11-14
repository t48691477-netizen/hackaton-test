package ru.cyber102.arinspector.ui.login

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.ui.components.BrandTopBar
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens

@Composable
fun LoginScreen(
    viewModel: LoginViewModel,
    onLoginSuccess: () -> Unit,
    onOpenSettings: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val invalidLengthMsg = stringResource(R.string.login_error_invalid_length)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        BrandTopBar(
            title = stringResource(R.string.brand_header_title),
            subtitle = stringResource(R.string.brand_company_subtitle),
            actions = {
                IconButton(
                    onClick = onOpenSettings,
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("login_settings_button")
                ) {
                    Icon(
                        imageVector = Icons.Filled.Settings,
                        contentDescription = stringResource(R.string.cd_settings),
                        tint = KstColors.White
                    )
                }
            }
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            EngineeringCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 480.dp)
            ) {
                Text(
                    text = stringResource(R.string.login_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = stringResource(R.string.login_subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextSecondary
                )

                Spacer(modifier = Modifier.height(20.dp))

                OutlinedTextField(
                    value = uiState.accessKey,
                    onValueChange = viewModel::onAccessKeyChanged,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("access_key_input"),
                    label = { Text(stringResource(R.string.login_key_label)) },
                    placeholder = { Text(stringResource(R.string.login_key_placeholder)) },
                    supportingText = {
                        Text(
                            text = stringResource(R.string.login_key_helper),
                            color = KstColors.TextSecondary
                        )
                    },
                    leadingIcon = {
                        Icon(
                            imageVector = Icons.Filled.Lock,
                            contentDescription = null,
                            tint = KstColors.TextSecondary
                        )
                    },
                    trailingIcon = {
                        IconButton(
                            onClick = viewModel::toggleKeyVisibility,
                            modifier = Modifier
                                .size(48.dp)
                                .testTag("toggle_key_visibility_button")
                        ) {
                            Icon(
                                painter = painterResource(
                                    if (uiState.isKeyVisible) {
                                        R.drawable.ic_visibility_off
                                    } else {
                                        R.drawable.ic_visibility
                                    }
                                ),
                                contentDescription = stringResource(
                                    if (uiState.isKeyVisible) R.string.login_hide_key else R.string.login_show_key
                                ),
                                tint = KstColors.TextSecondary
                            )
                        }
                    },
                    singleLine = true,
                    visualTransformation = if (uiState.isKeyVisible) {
                        VisualTransformation.None
                    } else {
                        PasswordVisualTransformation()
                    },
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Characters,
                        autoCorrectEnabled = false,
                        keyboardType = KeyboardType.Ascii,
                        imeAction = ImeAction.Done
                    ),
                    keyboardActions = KeyboardActions(
                        onDone = {
                            viewModel.submitLogin(invalidLengthMsg, onLoginSuccess)
                        }
                    ),
                    shape = PromScanShapesTokens.Control,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = KstColors.Accent,
                        unfocusedBorderColor = KstColors.Border,
                        focusedLabelColor = KstColors.Accent,
                        cursorColor = KstColors.Accent
                    ),
                    isError = uiState.errorMessage != null
                )

                val error = uiState.errorMessage
                if (!error.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Surface(
                        color = KstColors.ErrorTint,
                        shape = PromScanShapesTokens.Control,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = error,
                            color = KstColors.Error,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                if (uiState.isLoading) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(28.dp),
                            color = KstColors.Accent,
                            strokeWidth = 3.dp
                        )
                    }
                } else {
                    PrimaryActionButton(
                        text = stringResource(R.string.login_button),
                        onClick = { viewModel.submitLogin(invalidLengthMsg, onLoginSuccess) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp)
                            .testTag("login_submit_button")
                    )
                }
            }
        }
    }
}
