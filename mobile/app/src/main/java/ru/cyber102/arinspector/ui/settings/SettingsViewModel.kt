package ru.cyber102.arinspector.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.local.SettingsStore
import ru.cyber102.arinspector.data.model.AccountDto
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.data.repository.PromScanRepository

data class HealthCheckStatus(
    val isSuccess: Boolean,
    val message: String
)

data class SettingsUiState(
    val serverUrlInput: String = SettingsStore.DEFAULT_SERVER_URL,
    val analysisIntervalSec: Int = SettingsStore.DEFAULT_INTERVAL_SEC,
    val isCheckingHealth: Boolean = false,
    val healthStatus: HealthCheckStatus? = null,
    val account: AccountDto? = null,
    val isLoggingOut: Boolean = false
)

class SettingsViewModel(
    private val settingsStore: SettingsStore,
    private val repository: PromScanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        SettingsUiState(
            serverUrlInput = settingsStore.currentBaseUrl,
            analysisIntervalSec = settingsStore.currentIntervalSec,
            account = repository.currentAccount.value
        )
    )
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            settingsStore.settingsFlow.collect { settings ->
                _uiState.update {
                    it.copy(
                        serverUrlInput = settings.serverUrl,
                        analysisIntervalSec = settings.analysisIntervalSec
                    )
                }
            }
        }
        viewModelScope.launch {
            repository.currentAccount.collect { acc ->
                _uiState.update { it.copy(account = acc) }
            }
        }
    }

    fun onServerUrlChanged(value: String) {
        _uiState.update { it.copy(serverUrlInput = value, healthStatus = null) }
    }

    fun saveServerUrl(savedMessage: String) {
        viewModelScope.launch {
            val normalized = settingsStore.saveServerUrl(_uiState.value.serverUrlInput)
            _uiState.update {
                it.copy(
                    serverUrlInput = normalized,
                    healthStatus = HealthCheckStatus(isSuccess = true, message = savedMessage)
                )
            }
        }
    }

    fun checkHealth(okMessage: String) {
        viewModelScope.launch {
            val normalized = settingsStore.saveServerUrl(_uiState.value.serverUrlInput)
            _uiState.update {
                it.copy(
                    serverUrlInput = normalized,
                    isCheckingHealth = true,
                    healthStatus = null
                )
            }
            when (val result = repository.checkHealth()) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isCheckingHealth = false,
                            healthStatus = HealthCheckStatus(isSuccess = true, message = okMessage)
                        )
                    }
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isCheckingHealth = false,
                            healthStatus = HealthCheckStatus(isSuccess = false, message = result.message)
                        )
                    }
                }
            }
        }
    }

    fun selectInterval(seconds: Int) {
        viewModelScope.launch {
            settingsStore.saveAnalysisInterval(seconds)
            _uiState.update { it.copy(analysisIntervalSec = seconds) }
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        if (_uiState.value.isLoggingOut) return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoggingOut = true) }
            repository.logout()
            _uiState.update { it.copy(isLoggingOut = false) }
            onLoggedOut()
        }
    }

    class Factory(
        private val settingsStore: SettingsStore,
        private val repository: PromScanRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return SettingsViewModel(settingsStore, repository) as T
        }
    }
}
