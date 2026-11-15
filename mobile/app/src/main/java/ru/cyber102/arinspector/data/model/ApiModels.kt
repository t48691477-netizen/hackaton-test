package ru.cyber102.arinspector.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LoginRequest(
    @Json(name = "access_key") val accessKey: String
)

@JsonClass(generateAdapter = true)
data class LoginResponse(
    @Json(name = "session_token") val sessionToken: String? = null,
    @Json(name = "expires_at") val expiresAt: String? = null,
    @Json(name = "account") val account: AccountDto? = null
)

@JsonClass(generateAdapter = true)
data class AccountDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "full_name") val fullName: String? = null,
    @Json(name = "email") val email: String? = null,
    @Json(name = "role") val role: String? = null,
    @Json(name = "permissions") val permissions: List<String>? = null
) {
    fun hasPermission(permission: String): Boolean =
        permissions?.contains(permission) == true
}

@JsonClass(generateAdapter = true)
data class EquipmentSpecDto(
    @Json(name = "label") val label: String? = null,
    @Json(name = "value") val value: String? = null,
    @Json(name = "unit") val unit: String? = null
)

@JsonClass(generateAdapter = true)
data class EquipmentNodeDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "name") val name: String? = null,
    @Json(name = "specs") val specs: List<EquipmentSpecDto>? = null
)

@JsonClass(generateAdapter = true)
data class EquipmentDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "name") val name: String? = null,
    @Json(name = "inventory_number") val inventoryNumber: String? = null,
    @Json(name = "category") val category: String? = null,
    @Json(name = "location") val location: String? = null,
    @Json(name = "state") val state: String? = null,
    @Json(name = "manufacturer") val manufacturer: String? = null,
    @Json(name = "model") val model: String? = null,
    @Json(name = "commissioned_at") val commissionedAt: String? = null,
    @Json(name = "service_life_years") val serviceLifeYears: Int? = null,
    @Json(name = "last_maintenance_at") val lastMaintenanceAt: String? = null,
    @Json(name = "next_maintenance_at") val nextMaintenanceAt: String? = null,
    @Json(name = "specs") val specs: List<EquipmentSpecDto>? = null,
    @Json(name = "nodes") val nodes: List<EquipmentNodeDto>? = null,
    @Json(name = "created_at") val createdAt: String? = null,
    @Json(name = "updated_at") val updatedAt: String? = null
)

@JsonClass(generateAdapter = true)
data class DefectDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "label") val label: String? = null,
    @Json(name = "confidence") val confidence: Double? = null,
    @Json(name = "severity") val severity: String? = null,
    @Json(name = "bbox") val bbox: List<Double>? = null,
    @Json(name = "polygon") val polygon: List<List<Double>>? = null,
    @Json(name = "node_id") val nodeId: String? = null,
    @Json(name = "source_model") val sourceModel: String? = null,
    @Json(name = "recommendation") val recommendation: String? = null
)

@JsonClass(generateAdapter = true)
data class ConditionParametersDto(
    @Json(name = "oil_leak_probability") val oilLeakProbability: Double? = null,
    @Json(name = "rust_probability") val rustProbability: Double? = null,
    @Json(name = "poor_weld_probability") val poorWeldProbability: Double? = null
)

@JsonClass(generateAdapter = true)
data class LlmSummaryDto(
    @Json(name = "criticality") val criticality: String? = null,
    @Json(name = "probable_cause") val probableCause: String? = null,
    @Json(name = "recommendation_steps") val recommendationSteps: List<String>? = null
)

@JsonClass(generateAdapter = true)
data class InspectMetaDto(
    @Json(name = "vision_mode") val visionMode: String? = null,
    @Json(name = "llm_mode") val llmMode: String? = null,
    @Json(name = "models") val models: Map<String, String>? = null,
    @Json(name = "processing_ms") val processingMs: Int? = null,
    @Json(name = "analyzed_at") val analyzedAt: String? = null
)

@JsonClass(generateAdapter = true)
data class InspectResponse(
    @Json(name = "inspection_id") val inspectionId: String? = null,
    @Json(name = "equipment") val equipment: EquipmentDto? = null,
    @Json(name = "defects") val defects: List<DefectDto>? = null,
    @Json(name = "condition_parameters") val conditionParameters: ConditionParametersDto? = null,
    @Json(name = "llm") val llm: LlmSummaryDto? = null,
    @Json(name = "summary") val summary: String? = null,
    @Json(name = "meta") val meta: InspectMetaDto? = null
)

@JsonClass(generateAdapter = true)
data class AssigneeDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "full_name") val fullName: String? = null
)

@JsonClass(generateAdapter = true)
data class ReportDto(
    @Json(name = "id") val id: String? = null,
    @Json(name = "equipment_id") val equipmentId: String? = null,
    @Json(name = "inspection_id") val inspectionId: String? = null,
    @Json(name = "status") val status: String? = null,
    @Json(name = "comment") val comment: String? = null,
    @Json(name = "photo_url") val photoUrl: String? = null,
    @Json(name = "result") val result: InspectResponse? = null,
    @Json(name = "assignee") val assignee: AssigneeDto? = null,
    @Json(name = "started_at") val startedAt: String? = null,
    @Json(name = "completed_at") val completedAt: String? = null,
    @Json(name = "repair_comment") val repairComment: String? = null,
    @Json(name = "created_at") val createdAt: String? = null,
    @Json(name = "updated_at") val updatedAt: String? = null
)

@JsonClass(generateAdapter = true)
data class UpdateReportStatusRequest(
    @Json(name = "status") val status: String,
    @Json(name = "comment") val comment: String? = null
)

data class InspectOutcome(
    val parsed: InspectResponse,
    val rawJson: String
)
