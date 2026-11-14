package ru.cyber102.arinspector.ui.tasks

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.model.ReportDto
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.data.repository.PromScanRepository

data class TaskDetailUiState(
    val report: ReportDto? = null,
    val isLoading: Boolean = true,
    val isUpdatingStatus: Boolean = false,
    val showCompleteDialog: Boolean = false,
    val errorMessage: String? = null,
    val snackbarMessage: String? = null
)

class TaskDetailViewModel(
    private val reportId: String,
    private val repository: PromScanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(TaskDetailUiState())
    val uiState: StateFlow<TaskDetailUiState> = _uiState.asStateFlow()

    init {
        loadDetail()
    }

    fun loadDetail() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            when (val result = repository.getReport(reportId)) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            report = result.data,
                            isLoading = false,
                            errorMessage = null
                        )
                    }
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

    fun takeInWork() {
        updateStatus(status = "in_progress", comment = null)
    }

    fun setShowCompleteDialog(show: Boolean) {
        _uiState.update { it.copy(showCompleteDialog = show) }
    }

    fun completeTask(comment: String) {
        updateStatus(status = "closed", comment = comment.trim())
    }

    private fun updateStatus(status: String, comment: String?) {
        if (_uiState.value.isUpdatingStatus) return
        viewModelScope.launch {
            _uiState.update { it.copy(isUpdatingStatus = true) }
            when (val result = repository.updateReportStatus(reportId, status, comment)) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            report = result.data,
                            isUpdatingStatus = false,
                            showCompleteDialog = false
                        )
                    }
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isUpdatingStatus = false,
                            showCompleteDialog = false,
                            snackbarMessage = result.message
                        )
                    }
                }
            }
        }
    }

    fun resolvePhotoUrl(photoUrl: String?): String? = repository.resolveStaticUrl(photoUrl)

    fun consumeSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    class Factory(
        private val reportId: String,
        private val repository: PromScanRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return TaskDetailViewModel(reportId, repository) as T
        }
    }
}
