package ru.cyber102.arinspector.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.data.repository.PromScanRepository
import ru.cyber102.arinspector.util.QrParser

data class LoginUiState(
    val accessKey: String = "",
    val isKeyVisible: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

class LoginViewModel(
    private val repository: PromScanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onAccessKeyChanged(raw: String) {
        val sanitized = QrParser.sanitizeAccessKey(raw)
        _uiState.update {
            it.copy(accessKey = sanitized, errorMessage = null)
        }
    }

    fun toggleKeyVisibility() {
        _uiState.update { it.copy(isKeyVisible = !it.isKeyVisible) }
    }

    fun submitLogin(
        invalidLengthError: String,
        onSuccess: () -> Unit
    ) {
        val currentKey = _uiState.value.accessKey
        if (currentKey.length != 10) {
            _uiState.update { it.copy(errorMessage = invalidLengthError) }
            return
        }
        if (_uiState.value.isLoading) return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            when (val result = repository.login(currentKey)) {
                is ApiResult.Success -> {
                    _uiState.update { it.copy(isLoading = false) }
                    onSuccess()
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = result.message
                        )
                    }
                }
            }
        }
    }

    class Factory(
        private val repository: PromScanRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return LoginViewModel(repository) as T
        }
    }
}
