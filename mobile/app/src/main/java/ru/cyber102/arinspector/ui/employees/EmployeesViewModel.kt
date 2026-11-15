package ru.cyber102.arinspector.ui.employees

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.model.EmployeeDto
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.data.repository.PromScanRepository

data class EmployeesUiState(
    val employees: List<EmployeeDto> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val issuedKey: String? = null,
    val issuedFor: String? = null
)

class EmployeesViewModel(
    private val repository: PromScanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(EmployeesUiState())
    val uiState: StateFlow<EmployeesUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            when (val result = repository.getEmployees()) {
                is ApiResult.Success -> _uiState.update {
                    it.copy(employees = result.data, isLoading = false)
                }
                is ApiResult.Error -> _uiState.update {
                    it.copy(isLoading = false, errorMessage = result.message)
                }
            }
        }
    }

    fun create(fullName: String, email: String, role: String) {
        viewModelScope.launch {
            when (val result = repository.createEmployee(fullName.trim(), email.trim(), role)) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            issuedKey = result.data.accessKey,
                            issuedFor = result.data.employee.fullName,
                            errorMessage = null
                        )
                    }
                    load()
                }
                is ApiResult.Error -> _uiState.update { it.copy(errorMessage = result.message) }
            }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            when (val result = repository.deleteEmployee(id)) {
                is ApiResult.Success -> load()
                is ApiResult.Error -> _uiState.update { it.copy(errorMessage = result.message) }
            }
        }
    }

    fun dismissKey() {
        _uiState.update { it.copy(issuedKey = null, issuedFor = null) }
    }

    class Factory(
        private val repository: PromScanRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return EmployeesViewModel(repository) as T
        }
    }
}
