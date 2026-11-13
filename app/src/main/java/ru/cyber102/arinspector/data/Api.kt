package ru.cyber102.arinspector.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface CyberApi {

    @GET("api/equipment/{id}")
    suspend fun equipment(@Path("id") id: String): Equipment

    @POST("api/inspect")
    suspend fun inspect(@Body request: InspectRequest): InspectResponse

    @POST("api/reports")
    suspend fun report(@Body request: ReportRequest): ReportResponse

    /** Ассистент «Моттэл»: разбор находок, запчасти, оформление акта. */
    @POST("api/chat")
    suspend fun chat(@Body request: ChatRequest): ChatResponse

    @GET("api/health")
    suspend fun health(): HealthResponse
}

object QrParser {

    private val idRegex = Regex("""([A-Z][A-Z0-9]{1,15}-\d{1,6})""")

    /**
     * Принимает содержимое QR: чистый id (`PUMP-402`), URL с id или произвольный текст.
     * Возвращает нормализованный идентификатор оборудования.
     */
    fun equipmentId(raw: String): String {
        val value = raw.trim()
        if (value.isEmpty()) return ""
        idRegex.find(value.uppercase())?.let { return it.groupValues[1] }
        value.substringAfterLast('/').substringBefore('?').trim().let { tail ->
            if (tail.isNotEmpty()) return tail.uppercase().take(48)
        }
        return ""
    }
}
