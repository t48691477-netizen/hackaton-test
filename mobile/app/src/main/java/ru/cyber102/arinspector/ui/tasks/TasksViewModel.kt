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

enum class TaskStatusFilter(val queryParam: String?) {
    ALL(null),
    OPEN("open"),
    IN_PROGRESS("in_progress"),
    CLOSED("closed")
}

data class TasksUiState(
    val selectedFilter: TaskStatusFilter = TaskStatusFilter.ALL,
    val reports: List<ReportDto> = emptyList(),
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null
)

class TasksViewModel(
    private val repository: PromScanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(TasksUiState())
    val uiState: StateFlow<TasksUiState> = _uiState.asStateFlow()

    init {
        loadReports(isPullRefresh = false)
    }

    fun selectFilter(filter: TaskStatusFilter) {
        if (_uiState.value.selectedFilter == filter) return
        _uiState.update { it.copy(selectedFilter = filter) }
        loadReports(isPullRefresh = false)
    }

    fun loadReports(isPullRefresh: Boolean = false) {
        val filter = _uiState.value.selectedFilter
        viewModelScope.launch {
            _uiState.update {
                if (isPullRefresh) {
                    it.copy(isRefreshing = true, errorMessage = null)
                } else {
                    it.copy(isLoading = true, errorMessage = null)
                }
            }
            when (val result = repository.getReports(filter.queryParam)) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            reports = result.data,
                            isLoading = false,
                            isRefreshing = false,
                            errorMessage = null
                        )
                    }
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            isRefreshing = false,
                            errorMessage = result.message
                        )
                    }
                }
            }
        }
    }

    fun resolvePhotoUrl(photoUrl: String?): String? = repository.resolveStaticUrl(photoUrl)

    class Factory(
        private val repository: PromScanRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return TasksViewModel(repository) as T
        }
    }
}
