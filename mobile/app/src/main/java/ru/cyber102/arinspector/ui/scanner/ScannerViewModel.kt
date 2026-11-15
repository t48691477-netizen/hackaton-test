package ru.cyber102.arinspector.ui.scanner

import android.os.SystemClock
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.local.SettingsStore
import ru.cyber102.arinspector.data.model.EquipmentDto
import ru.cyber102.arinspector.data.model.InspectResponse
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.data.repository.PromScanRepository
import ru.cyber102.arinspector.util.CapturedFrame
import java.util.concurrent.atomic.AtomicBoolean

data class ScannerUiState(
    val equipment: EquipmentDto? = null,
    val isEquipmentLoading: Boolean = false,
    val showPassportSheet: Boolean = false,
    val isAnalyzing: Boolean = false,
    val isInspectInFlight: Boolean = false,
    val frameWidth: Int = 0,
    val frameHeight: Int = 0,
    val latestInspection: InspectResponse? = null,
    val latestRawJson: String? = null,
    val lastFrameJpeg: ByteArray? = null,
    val isCreatingReport: Boolean = false,
    val showManualIdDialog: Boolean = false,
    val equipmentOptions: List<EquipmentDto> = emptyList(),
    val showCreateReportDialog: Boolean = false,
    val snackbarMessage: String? = null,
    val analysisIntervalSec: Int = SettingsStore.DEFAULT_INTERVAL_SEC
)

class ScannerViewModel(
    private val repository: PromScanRepository,
    private val settingsStore: SettingsStore
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScannerUiState())
    val uiState: StateFlow<ScannerUiState> = _uiState.asStateFlow()

    private val inspectInFlightFlag = AtomicBoolean(false)

    @Volatile
    private var lastInspectCompletedAtMs: Long = 0L

    @Volatile
    private var lastQrValue: String? = null

    @Volatile
    private var lastQrDetectedAtMs: Long = 0L

    init {
        viewModelScope.launch {
            settingsStore.settingsFlow.collect { settings ->
                _uiState.update { it.copy(analysisIntervalSec = settings.analysisIntervalSec) }
            }
        }
    }

    fun updateFrameDimensions(width: Int, height: Int) {
        val current = _uiState.value
        if (current.frameWidth != width || current.frameHeight != height) {
            _uiState.update { it.copy(frameWidth = width, frameHeight = height) }
        }
    }

    fun onQrDetected(equipmentId: String) {
        val now = SystemClock.elapsedRealtime()
        if (equipmentId == lastQrValue && now - lastQrDetectedAtMs < 2500L) return
        if (_uiState.value.isEquipmentLoading) return

        lastQrValue = equipmentId
        lastQrDetectedAtMs = now
        loadEquipment(equipmentId)
    }

    fun loadEquipment(equipmentId: String) {
        val trimmed = equipmentId.trim()
        if (trimmed.isEmpty()) return

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isEquipmentLoading = true,
                    showManualIdDialog = false
                )
            }
            when (val result = repository.getEquipment(trimmed)) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            equipment = result.data,
                            isEquipmentLoading = false,
                            showPassportSheet = true,
                            isAnalyzing = false,
                            latestInspection = null,
                            latestRawJson = null,
                            lastFrameJpeg = null
                        )
                    }
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isEquipmentLoading = false,
                            snackbarMessage = result.message
                        )
                    }
                }
            }
        }
    }

    fun clearEquipment() {
        _uiState.update {
            it.copy(
                equipment = null,
                showPassportSheet = false,
                isAnalyzing = false,
                latestInspection = null,
                latestRawJson = null,
                lastFrameJpeg = null
            )
        }
        lastQrValue = null
    }

    fun openPassportSheet(show: Boolean) {
        _uiState.update { it.copy(showPassportSheet = show) }
    }

    fun toggleAnalysis() {
        val eq = _uiState.value.equipment ?: return
        if (eq.id.isNullOrBlank()) return
        val next = !_uiState.value.isAnalyzing
        if (next) {
            lastInspectCompletedAtMs = 0L
        }
        _uiState.update {
            it.copy(
                isAnalyzing = next,
                showPassportSheet = false
            )
        }
    }

    /**
     * Проверяет, пора ли захватывать очередной кадр для анализа (не чаще заданного интервала
     * и строго после завершения предыдущего запроса).
     */
    fun tryAcquireFrameCaptureSlot(): Boolean {
        val state = _uiState.value
        if (!state.isAnalyzing || state.equipment?.id.isNullOrBlank()) return false
        val now = SystemClock.elapsedRealtime()
        val intervalMs = state.analysisIntervalSec * 1000L
        if (lastInspectCompletedAtMs != 0L && now - lastInspectCompletedAtMs < intervalMs) {
            return false
        }
        return inspectInFlightFlag.compareAndSet(false, true)
    }

    fun releaseFrameCaptureSlotOnError() {
        lastInspectCompletedAtMs = SystemClock.elapsedRealtime()
        inspectInFlightFlag.set(false)
    }

    fun submitCapturedFrame(frame: CapturedFrame) {
        val equipmentId = _uiState.value.equipment?.id
        if (equipmentId.isNullOrBlank()) {
            releaseFrameCaptureSlotOnError()
            return
        }

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isInspectInFlight = true,
                    frameWidth = frame.width,
                    frameHeight = frame.height,
                    lastFrameJpeg = frame.jpegBytes
                )
            }
            try {
                when (val result = repository.inspectFrame(frame.jpegBytes, equipmentId)) {
                    is ApiResult.Success -> {
                        _uiState.update {
                            it.copy(
                                isInspectInFlight = false,
                                latestInspection = result.data.parsed,
                                latestRawJson = result.data.rawJson
                            )
                        }
                    }
                    is ApiResult.Error -> {
                        _uiState.update {
                            it.copy(
                                isInspectInFlight = false,
                                snackbarMessage = result.message
                            )
                        }
                    }
                }
            } finally {
                lastInspectCompletedAtMs = SystemClock.elapsedRealtime()
                inspectInFlightFlag.set(false)
            }
        }
    }

    fun setShowManualIdDialog(show: Boolean) {
        _uiState.update { it.copy(showManualIdDialog = show) }
        if (show) {
            viewModelScope.launch {
                val result = repository.getEquipmentList()
                if (result is ApiResult.Success) {
                    _uiState.update { it.copy(equipmentOptions = result.data) }
                }
            }
        }
    }

    fun setShowCreateReportDialog(show: Boolean, noFrameMessage: String? = null) {
        if (show && (_uiState.value.latestRawJson.isNullOrBlank() || _uiState.value.equipment?.id.isNullOrBlank())) {
            _uiState.update { it.copy(snackbarMessage = noFrameMessage) }
            return
        }
        _uiState.update { it.copy(showCreateReportDialog = show) }
    }

    fun createReport(
        comment: String,
        successMessage: String,
        onCreated: () -> Unit
    ) {
        val state = _uiState.value
        val equipmentId = state.equipment?.id ?: return
        val inspectionId = state.latestInspection?.inspectionId ?: ""
        val rawPayload = state.latestRawJson ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isCreatingReport = true) }
            val result = repository.createReport(
                equipmentId = equipmentId,
                inspectionId = inspectionId,
                comment = comment.trim(),
                payloadRawJson = rawPayload,
                photoJpeg = state.lastFrameJpeg
            )
            when (result) {
                is ApiResult.Success -> {
                    _uiState.update {
                        it.copy(
                            isCreatingReport = false,
                            showCreateReportDialog = false,
                            isAnalyzing = false,
                            snackbarMessage = successMessage
                        )
                    }
                    onCreated()
                }
                is ApiResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isCreatingReport = false,
                            snackbarMessage = result.message
                        )
                    }
                }
            }
        }
    }

    fun showMessage(message: String) {
        _uiState.update { it.copy(snackbarMessage = message) }
    }

    fun consumeSnackbar() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    class Factory(
        private val repository: PromScanRepository,
        private val settingsStore: SettingsStore
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ScannerViewModel(repository, settingsStore) as T
        }
    }
}
