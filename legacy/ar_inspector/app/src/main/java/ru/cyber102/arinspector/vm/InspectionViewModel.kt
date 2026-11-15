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
import ru.cyber102.arinspector.data.ChatRequest
import ru.cyber102.arinspector.data.ChatTurn
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.data.EquipmentRepository
import ru.cyber102.arinspector.data.HealthResponse
import ru.cyber102.arinspector.data.InspectResponse
import ru.cyber102.arinspector.data.QrParser
import ru.cyber102.arinspector.data.ReportRequest
import ru.cyber102.arinspector.data.ReportResponse
import ru.cyber102.arinspector.data.ResolutionStatus
import ru.cyber102.arinspector.util.ImageUtils
import java.io.File
import java.time.Instant
import java.util.UUID

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

    private val _documentUploading = MutableStateFlow(false)
    val documentUploading: StateFlow<Boolean> = _documentUploading.asStateFlow()

    private val _documentUploadError = MutableStateFlow<String?>(null)
    val documentUploadError: StateFlow<String?> = _documentUploadError.asStateFlow()

    private var pendingReportIdempotencyKey: String? = null
    private var pendingReportFingerprint: String? = null

    private val _assistantOpen = MutableStateFlow(false)
    val assistantOpen: StateFlow<Boolean> = _assistantOpen.asStateFlow()

    private val _chat = MutableStateFlow(
        listOf(
            ChatTurn(
                role = "mottel",
                text = "Моттэл на связи. Я инженерный ассистент: разберу находки, " +
                    "соберу список запчастей, подскажу по акту."
            )
        )
    )
    val chat: StateFlow<List<ChatTurn>> = _chat.asStateFlow()

    private val _chatBusy = MutableStateFlow(false)
    val chatBusy: StateFlow<Boolean> = _chatBusy.asStateFlow()

    private val _serverHealth = MutableStateFlow<HealthResponse?>(null)
    val serverHealth: StateFlow<HealthResponse?> = _serverHealth.asStateFlow()

    val currentBaseUrl: String get() = settings.normalizedBaseUrl()

    fun refreshHealth() {
        viewModelScope.launch {
            val result = repository.health()
            _serverHealth.value = result.data
            Log.i(
                TAG,
                "health: mode=${result.data.mode} model=${result.data.model} demo=${result.fromDemo}"
            )
        }
    }

    fun openAssistant() {
        _assistantOpen.value = true
        refreshHealth()
    }

    fun closeAssistant() {
        _assistantOpen.value = false
    }

    fun askAssistant(question: String) {
        val text = question.trim()
        if (text.isEmpty() || _chatBusy.value) return
        viewModelScope.launch {
            _chatBusy.value = true
            _chat.value = _chat.value + ChatTurn("user", text)
            runCatching {
                repository.chat(
                    ChatRequest(
                        message = text,
                        equipmentId = _equipment.value?.id,
                        history = _chat.value.takeLast(8)
                    )
                )
            }.onSuccess { result ->
                _chat.value = _chat.value + ChatTurn("mottel", result.data.reply)
                Log.i(TAG, "chat: model=${result.data.model} demo=${result.fromDemo}")
            }.onFailure { error ->
                _chat.value = _chat.value + ChatTurn(
                    "mottel",
                    "Не удалось получить ответ от сервера. Проверьте сеть и режим подключения."
                )
                Log.w(TAG, "chat request failed", error)
            }
            _chatBusy.value = false
        }
    }

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
            runCatching { repository.equipment(id) }
                .onSuccess { result ->
                    _equipment.value = result.data
                    _demoResponse.value = result.fromDemo
                    Log.i(
                        TAG,
                        "equipment ${result.data.id}: components=${result.data.components.size} " +
                            "demo=${result.fromDemo}"
                    )
                }
                .onFailure { error ->
                    _error.value = "Не удалось загрузить оборудование"
                    _equipment.value = null
                    Log.w(TAG, "equipment request failed", error)
                }
            _loading.value = false
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
            pendingReportIdempotencyKey = null
            pendingReportFingerprint = null
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
            pendingReportIdempotencyKey = null
            pendingReportFingerprint = null
            val prepared = withContext(Dispatchers.Default) {
                jpeg?.let { ImageUtils.jpegToUploadJpeg(it, rotationDegrees, screenAspect) }
            }
            runInspection(equipmentId, prepared, screenAspect)
        }
    }

    private suspend fun runInspection(equipmentId: String, jpeg: ByteArray?, aspect: Float) {
        runCatching { repository.inspect(equipmentId, jpeg, aspect) }
            .onSuccess { result ->
                _inspection.value = result.data
                _demoResponse.value = _demoResponse.value || result.fromDemo
                Log.i(
                    TAG,
                    "inspect $equipmentId: status=${result.data.status} " +
                        "defects=${result.data.defects.size} jpeg=${jpeg?.size ?: 0}B " +
                        "demo=${result.fromDemo}"
                )
            }
            .onFailure { error ->
                _error.value = "Не удалось выполнить осмотр"
                Log.w(TAG, "inspect request failed", error)
            }
        _scanning.value = false
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
                inspectionId = _inspection.value?.inspectionId,
                nodeId = componentId,
                defectId = defect?.id,
                status = status.apiValue,
                comment = comment.ifBlank { null },
                defectTitle = defect?.displayTitle,
                createdAt = Instant.now().toString(),
                idempotencyKey = reportFingerprint(
                    equipmentId, componentId, defect, status, comment
                ).let { fingerprint ->
                    if (fingerprint != pendingReportFingerprint || pendingReportIdempotencyKey == null) {
                        pendingReportFingerprint = fingerprint
                        pendingReportIdempotencyKey = UUID.randomUUID().toString()
                    }
                    pendingReportIdempotencyKey
                }
            )
            runCatching { repository.report(request) }
                .onSuccess { result ->
                    _report.value = result.data
                    _demoResponse.value = _demoResponse.value || result.fromDemo
                    Log.i(TAG, "report ${result.data.reportId} status=${result.data.status} demo=${result.fromDemo}")
                }
                .onFailure { error ->
                    _error.value = "Не удалось сохранить акт"
                    Log.w(TAG, "report request failed", error)
                }
            _reporting.value = false
        }
    }

    /** Upload the device-generated PDF; sharing remains available offline. */
    fun uploadReportDocument(reportId: String, file: File) {
        if (_documentUploading.value) return
        viewModelScope.launch {
            _documentUploading.value = true
            _documentUploadError.value = null
            runCatching {
                repository.uploadReportDocument(reportId, file.readBytes())
            }.onSuccess { result ->
                Log.i(
                    TAG,
                    "document ${result.data.objectKey}: ${result.data.byteSize}B " +
                        "demo=${result.fromDemo}"
                )
            }.onFailure { error ->
                _documentUploadError.value = "Не удалось сохранить PDF на сервере"
                Log.w(TAG, "document upload failed", error)
            }
            _documentUploading.value = false
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
        pendingReportIdempotencyKey = null
        pendingReportFingerprint = null
    }

    fun clearReport() {
        _report.value = null
        pendingReportIdempotencyKey = null
        pendingReportFingerprint = null
        _documentUploadError.value = null
    }

    /** Возврат со сканера: не должно быть автоперехода обратно в AR. */
    fun consumeEquipment() {
        _equipment.value = null
        _inspection.value = null
        _report.value = null
        _error.value = null
        pendingReportIdempotencyKey = null
        pendingReportFingerprint = null
        _documentUploadError.value = null
    }

    private fun reportFingerprint(
        equipmentId: String,
        componentId: String?,
        defect: Defect?,
        status: ResolutionStatus,
        comment: String
    ): String = listOf(
        equipmentId,
        _inspection.value?.inspectionId.orEmpty(),
        componentId.orEmpty(),
        defect?.id.orEmpty(),
        defect?.displayTitle.orEmpty(),
        status.apiValue,
        comment.trim()
    ).joinToString("\u0000")

    private companion object {
        const val TAG = "AR-Inspector"
    }
}
