package ru.cyber102.arinspector.vm

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.cyber102.arinspector.data.AppSettings
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.data.EquipmentRepository
import ru.cyber102.arinspector.data.InspectResponse
import ru.cyber102.arinspector.data.QrParser
import ru.cyber102.arinspector.data.ReportRequest
import ru.cyber102.arinspector.data.ReportResponse
import ru.cyber102.arinspector.data.ResolutionStatus
import ru.cyber102.arinspector.util.ImageUtils
import java.time.Instant

class InspectionViewModel(application: Application) : AndroidViewModel(application) {

    val settings = AppSettings(application)
    private val repository = EquipmentRepository(application, settings)

    private val _equipment = MutableStateFlow<Equipment?>(null)
    val equipment: StateFlow<Equipment?> = _equipment.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _demoMode = MutableStateFlow(settings.demoMode)
    val demoMode: StateFlow<Boolean> = _demoMode.asStateFlow()

    private val _demoResponse = MutableStateFlow(false)
    val demoResponse: StateFlow<Boolean> = _demoResponse.asStateFlow()

    private val _inspection = MutableStateFlow<InspectResponse?>(null)
    val inspection: StateFlow<InspectResponse?> = _inspection.asStateFlow()

    private val _scanning = MutableStateFlow(false)
    val scanning: StateFlow<Boolean> = _scanning.asStateFlow()

    private val _report = MutableStateFlow<ReportResponse?>(null)
    val report: StateFlow<ReportResponse?> = _report.asStateFlow()

    private val _reporting = MutableStateFlow(false)
    val reporting: StateFlow<Boolean> = _reporting.asStateFlow()

    val currentBaseUrl: String get() = settings.normalizedBaseUrl()

    fun loadEquipment(raw: String) {
        val id = QrParser.equipmentId(raw)
        if (id.isBlank()) {
            _error.value = "Не удалось распознать код оборудования"
            return
        }
        if (_loading.value) return
        viewModelScope.launch {
            _loading.value = true
            _error.value = null
            _inspection.value = null
            val result = repository.equipment(id)
            _equipment.value = result.data
            _demoResponse.value = result.fromDemo
            _loading.value = false
            Log.i(
                TAG,
                "equipment ${result.data.id}: components=${result.data.components.size} " +
                    "demo=${result.fromDemo}"
            )
        }
    }

    fun inspectWithYuv(
        equipmentId: String,
        frame: ImageUtils.YuvFrame?,
        rotationDegrees: Int,
        screenAspect: Float
    ) {
        viewModelScope.launch {
            _scanning.value = true
            _error.value = null
            _report.value = null
            val jpeg = withContext(Dispatchers.Default) {
                frame?.let { ImageUtils.yuvToUploadJpeg(it, rotationDegrees, screenAspect) }
            }
            runInspection(equipmentId, jpeg, screenAspect)
        }
    }

    fun inspectWithJpeg(
        equipmentId: String,
        jpeg: ByteArray?,
        rotationDegrees: Int,
        screenAspect: Float
    ) {
        viewModelScope.launch {
            _scanning.value = true
            _error.value = null
            _report.value = null
            val prepared = withContext(Dispatchers.Default) {
                jpeg?.let { ImageUtils.jpegToUploadJpeg(it, rotationDegrees, screenAspect) }
            }
            runInspection(equipmentId, prepared, screenAspect)
        }
    }

    private suspend fun runInspection(equipmentId: String, jpeg: ByteArray?, aspect: Float) {
        val result = repository.inspect(equipmentId, jpeg, aspect)
        _inspection.value = result.data
        _demoResponse.value = _demoResponse.value || result.fromDemo
        _scanning.value = false
        Log.i(
            TAG,
            "inspect $equipmentId: status=${result.data.status} " +
                "defects=${result.data.defects.size} jpeg=${jpeg?.size ?: 0}B " +
                "demo=${result.fromDemo}"
        )
    }

    fun submitReport(
        equipmentId: String,
        componentId: String?,
        defect: Defect?,
        status: ResolutionStatus,
        comment: String
    ) {
        if (_reporting.value) return
        viewModelScope.launch {
            _reporting.value = true
            _error.value = null
            val request = ReportRequest(
                equipmentId = equipmentId,
                nodeId = componentId,
                defectId = defect?.id,
                status = status.apiValue,
                comment = comment.ifBlank { null },
                defectTitle = defect?.displayTitle,
                createdAt = Instant.now().toString()
            )
            val result = repository.report(request)
            _report.value = result.data
            _demoResponse.value = _demoResponse.value || result.fromDemo
            _reporting.value = false
            Log.i(TAG, "report ${result.data.reportId} status=${result.data.status} demo=${result.fromDemo}")
        }
    }

    fun setDemoMode(enabled: Boolean) {
        settings.demoMode = enabled
        _demoMode.value = enabled
    }

    fun setBaseUrl(url: String) {
        settings.baseUrl = url
    }

    fun clearError() {
        _error.value = null
    }

    fun clearInspection() {
        _inspection.value = null
        _report.value = null
    }

    fun clearReport() {
        _report.value = null
    }

    /** Возврат со сканера: не должно быть автоперехода обратно в AR. */
    fun consumeEquipment() {
        _equipment.value = null
        _inspection.value = null
        _report.value = null
        _error.value = null
    }

    private companion object {
        const val TAG = "AR-Inspector"
    }
}
