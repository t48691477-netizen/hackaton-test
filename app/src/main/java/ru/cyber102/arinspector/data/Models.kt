package ru.cyber102.arinspector.data

import com.google.gson.annotations.SerializedName

/** Смещение узла относительно QR-якоря в метрах. */
data class Offset3(
    val x: Float = 0f,
    val y: Float = 0f,
    val z: Float = 0f
)

data class EquipmentComponent(
    val id: String = "",
    val name: String = "",
    @SerializedName("offset_from_qr")
    val offsetFromQr: Offset3 = Offset3(),
    /** Радиус зоны узла в метрах — используется для привязки дефектов. */
    val radius: Float = 0.25f,
    val description: String? = null
)

data class Equipment(
    val id: String = "",
    val name: String = "",
    val location: String? = null,
    val components: List<EquipmentComponent> = emptyList()
)

data class NormalizedPoint(
    val x: Float = 0f,
    val y: Float = 0f
)

data class Defect(
    val id: String = "",
    @SerializedName("node_id")
    val nodeId: String? = null,
    val type: String = "rust",
    val title: String? = null,
    val confidence: Float = 0.9f,
    val severity: String = "medium",
    /** Нормализованный полигон в координатах экрана (0..1). */
    val polygon: List<NormalizedPoint> = emptyList(),
    /** Нормализованный bbox [left, top, right, bottom]. */
    val bbox: List<Float>? = null,
    @SerializedName("offset_from_qr")
    val offsetFromQr: Offset3? = null,
    val analysis: String? = null,
    val recommendation: String? = null
) {
    val displayTitle: String
        get() = title ?: when (type.lowercase()) {
            "rust" -> "Коррозия"
            "crack" -> "Трещина"
            "leak" -> "Течь"
            "wear" -> "Износ"
            else -> type.replaceFirstChar { it.uppercaseChar() }
        }

    val isCritical: Boolean
        get() = severity.equals("high", true) || severity.equals("critical", true)

    fun rect(): List<Float>? {
        if (bbox != null && bbox.size >= 4) return bbox
        if (polygon.isEmpty()) return null
        val xs = polygon.map { it.x }
        val ys = polygon.map { it.y }
        return listOf(xs.min(), ys.min(), xs.max(), ys.max())
    }
}

data class InspectRequest(
    @SerializedName("equipment_id")
    val equipmentId: String,
    @SerializedName("image_base64")
    val imageBase64: String? = null,
    @SerializedName("image_width")
    val imageWidth: Int? = null,
    @SerializedName("image_height")
    val imageHeight: Int? = null,
    @SerializedName("screen_aspect")
    val screenAspect: Float? = null
)

data class InspectResponse(
    val status: String = "ok",
    val defects: List<Defect> = emptyList(),
    /** Общий инженерный вывод LLM по кадру. */
    val analysis: String? = null,
    @SerializedName("inspected_at")
    val inspectedAt: String? = null,
    @SerializedName("model")
    val model: String? = null
) {
    val isCritical: Boolean
        get() = status.equals("high", true) || status.equals("critical", true)

    val defectCount: Int get() = defects.size
}

enum class ResolutionStatus(val apiValue: String, val label: String) {
    FIXED("fixed_on_site", "Исправлено на месте"),
    PARTS("parts_required", "Требует заказа запчастей"),
    FALSE_POSITIVE("false_positive", "Ложное срабатывание")
}

data class ReportRequest(
    @SerializedName("equipment_id")
    val equipmentId: String,
    @SerializedName("node_id")
    val nodeId: String? = null,
    @SerializedName("defect_id")
    val defectId: String? = null,
    val status: String,
    val comment: String? = null,
    @SerializedName("defect_title")
    val defectTitle: String? = null,
    @SerializedName("created_at")
    val createdAt: String? = null
)

data class ReportResponse(
    @SerializedName("report_id")
    val reportId: String = "",
    val status: String = "",
    @SerializedName("created_at")
    val createdAt: String? = null
)

/** Результат запроса + признак, что ответ собран локальным демо-источником. */
data class Fetched<T>(
    val data: T,
    val fromDemo: Boolean
)

/** Одно сообщение диалога с ассистентом «Моттэл». */
data class ChatTurn(
    /** "user" | "mottel" */
    val role: String,
    val text: String
)

data class ChatRequest(
    val message: String,
    @SerializedName("equipment_id")
    val equipmentId: String? = null,
    val history: List<ChatTurn> = emptyList()
)

data class ChatResponse(
    val reply: String = "",
    val model: String? = null
)

data class HealthResponse(
    val status: String = "",
    /** "live" — реальная модель, "mock" — заранее подготовленные ответы. */
    val mode: String = "mock",
    val model: String? = null,
    val time: String? = null
) {
    val isLive: Boolean get() = mode.equals("live", true)
}
