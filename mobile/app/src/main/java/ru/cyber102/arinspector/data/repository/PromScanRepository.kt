package ru.cyber102.arinspector.data.repository

import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import retrofit2.Response
import ru.cyber102.arinspector.data.local.SettingsStore
import ru.cyber102.arinspector.data.local.TokenStore
import ru.cyber102.arinspector.data.model.AccountDto
import ru.cyber102.arinspector.data.model.EquipmentDto
import ru.cyber102.arinspector.data.model.InspectOutcome
import ru.cyber102.arinspector.data.model.InspectResponse
import ru.cyber102.arinspector.data.model.LoginRequest
import ru.cyber102.arinspector.data.model.LoginResponse
import ru.cyber102.arinspector.data.model.ReportDto
import ru.cyber102.arinspector.data.model.UpdateReportStatusRequest
import ru.cyber102.arinspector.data.remote.PromScanApi
import java.io.IOException

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(
        val message: String,
        val httpCode: Int? = null,
        val isNetworkError: Boolean = false
    ) : ApiResult<Nothing>()
}

class PromScanRepository(
    private val api: PromScanApi,
    private val moshi: Moshi,
    private val tokenStore: TokenStore,
    private val settingsStore: SettingsStore
) {
    private val _currentAccount = MutableStateFlow<AccountDto?>(null)
    val currentAccount: StateFlow<AccountDto?> = _currentAccount.asStateFlow()

    private val _unauthorizedEvents = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val unauthorizedEvents: SharedFlow<Unit> = _unauthorizedEvents.asSharedFlow()

    fun hasStoredToken(): Boolean = !tokenStore.getToken().isNullOrBlank()

    fun resolveStaticUrl(pathOrUrl: String?): String? {
        if (pathOrUrl.isNullOrBlank()) return null
        if (pathOrUrl.startsWith("http://", ignoreCase = true) ||
            pathOrUrl.startsWith("https://", ignoreCase = true)
        ) {
            return pathOrUrl
        }
        val base = settingsStore.currentBaseUrl.trimEnd('/')
        val rel = if (pathOrUrl.startsWith("/")) pathOrUrl else "/$pathOrUrl"
        return "$base$rel"
    }

    suspend fun login(accessKey: String): ApiResult<LoginResponse> {
        return try {
            val response = api.login(LoginRequest(accessKey))
            if (response.isSuccessful) {
                val body = response.body()
                val token = body?.sessionToken
                if (body != null && !token.isNullOrBlank()) {
                    tokenStore.saveToken(token)
                    _currentAccount.value = body.account
                    ApiResult.Success(body)
                } else {
                    ApiResult.Error("Пустой ответ от сервера", response.code())
                }
            } else {
                val msg = when (response.code()) {
                    401 -> "Ключ не подошёл"
                    429 -> "Слишком много попыток, повторите позже"
                    503 -> "Сервис входа недоступен"
                    else -> parseErrorMessage(response)
                }
                ApiResult.Error(msg, response.code())
            }
        } catch (_: IOException) {
            ApiResult.Error("Нет связи с сервером", isNetworkError = true)
        } catch (e: Exception) {
            ApiResult.Error(e.localizedMessage ?: "Ошибка входа")
        }
    }

    suspend fun fetchMe(): ApiResult<AccountDto> {
        return safeCall(notifyUnauthorized = false) {
            api.me()
        }.also { result ->
            when (result) {
                is ApiResult.Success -> _currentAccount.value = result.data
                is ApiResult.Error -> {
                    if (result.httpCode == 401) {
                        tokenStore.clearToken()
                        _currentAccount.value = null
                    }
                }
            }
        }
    }

    suspend fun logout() {
        try {
            api.logout()
        } catch (_: Exception) {
            // Игнорируем сетевые сбои при выходе — локальная сессия в любом случае очищается.
        } finally {
            tokenStore.clearToken()
            _currentAccount.value = null
        }
    }

    suspend fun checkHealth(): ApiResult<Unit> {
        return try {
            val response = api.health()
            if (response.isSuccessful) {
                ApiResult.Success(Unit)
            } else {
                ApiResult.Error(parseErrorMessage(response), response.code())
            }
        } catch (_: IOException) {
            ApiResult.Error("Нет связи с сервером", isNetworkError = true)
        } catch (e: Exception) {
            ApiResult.Error(e.localizedMessage ?: "Ошибка проверки сервера")
        }
    }

    suspend fun getEquipment(id: String): ApiResult<EquipmentDto> {
        return safeCall { api.getEquipment(id) }.let { result ->
            if (result is ApiResult.Error && result.httpCode == 404) {
                ApiResult.Error("Оборудование не найдено", httpCode = 404)
            } else {
                result
            }
        }
    }

    suspend fun getEquipmentList(): ApiResult<List<EquipmentDto>> {
        return safeCall { api.getEquipmentList() }
    }

    suspend fun inspectFrame(
        jpegBytes: ByteArray,
        equipmentId: String
    ): ApiResult<InspectOutcome> {
        return try {
            val filePart = MultipartBody.Part.createFormData(
                "file",
                "frame.jpg",
                jpegBytes.toRequestBody("image/jpeg".toMediaType())
            )
            val equipmentPart = MultipartBody.Part.createFormData("equipment_id", equipmentId)

            val response = api.inspectFrame(filePart, equipmentPart)
            if (response.isSuccessful) {
                val rawJson = response.body()?.string().orEmpty()
                if (rawJson.isBlank()) {
                    return ApiResult.Error("Пустой ответ анализа", response.code())
                }
                val parsed = moshi.adapter(InspectResponse::class.java).fromJson(rawJson)
                    ?: return ApiResult.Error("Не удалось разобрать ответ сервера", response.code())
                ApiResult.Success(
                    InspectOutcome(
                        parsed = parsed,
                        rawJson = rawJson
                    )
                )
            } else {
                handleErrorResponse(response, notifyUnauthorized = true)
            }
        } catch (_: IOException) {
            ApiResult.Error("Нет связи с сервером", isNetworkError = true)
        } catch (e: Exception) {
            ApiResult.Error(e.localizedMessage ?: "Ошибка анализа кадра")
        }
    }

    suspend fun createReport(
        equipmentId: String,
        inspectionId: String,
        comment: String,
        payloadRawJson: String,
        photoJpeg: ByteArray?
    ): ApiResult<ReportDto> {
        val equipmentPart = MultipartBody.Part.createFormData("equipment_id", equipmentId)
        val inspectionPart = MultipartBody.Part.createFormData("inspection_id", inspectionId)
        val statusPart = MultipartBody.Part.createFormData("status", "open")
        val commentPart = MultipartBody.Part.createFormData("comment", comment)
        val payloadPart = MultipartBody.Part.createFormData("payload", payloadRawJson)
        val assigneeId = _currentAccount.value?.id?.takeIf { it.isNotBlank() }
        val assigneePart = assigneeId?.let {
            MultipartBody.Part.createFormData("assignee_id", it)
        }
        val photoPart = photoJpeg?.let { bytes ->
            MultipartBody.Part.createFormData(
                "photo",
                "frame.jpg",
                bytes.toRequestBody("image/jpeg".toMediaType())
            )
        }

        return safeCall {
            api.createReport(
                equipmentId = equipmentPart,
                inspectionId = inspectionPart,
                status = statusPart,
                comment = commentPart,
                payload = payloadPart,
                assigneeId = assigneePart,
                photo = photoPart
            )
        }
    }

    suspend fun getReports(status: String? = null): ApiResult<List<ReportDto>> {
        return safeCall { api.getReports(status) }
    }

    suspend fun getReport(id: String): ApiResult<ReportDto> {
        return safeCall { api.getReport(id) }
    }

    suspend fun updateReportStatus(
        id: String,
        status: String,
        comment: String? = null
    ): ApiResult<ReportDto> {
        return safeCall {
            api.updateReportStatus(id, UpdateReportStatusRequest(status = status, comment = comment))
        }
    }

    private suspend fun <T> safeCall(
        notifyUnauthorized: Boolean = true,
        call: suspend () -> Response<T>
    ): ApiResult<T> {
        return try {
            val response = call()
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    ApiResult.Success(body)
                } else {
                    ApiResult.Error("Пустой ответ от сервера", response.code())
                }
            } else {
                handleErrorResponse(response, notifyUnauthorized)
            }
        } catch (_: IOException) {
            ApiResult.Error("Нет связи с сервером", isNetworkError = true)
        } catch (e: Exception) {
            ApiResult.Error(e.localizedMessage ?: "Ошибка сети")
        }
    }

    private fun <T> handleErrorResponse(
        response: Response<T>,
        notifyUnauthorized: Boolean
    ): ApiResult.Error {
        if (response.code() == 401 && notifyUnauthorized) {
            tokenStore.clearToken()
            _currentAccount.value = null
            _unauthorizedEvents.tryEmit(Unit)
        }
        return ApiResult.Error(
            message = parseErrorMessage(response),
            httpCode = response.code()
        )
    }

    private fun parseErrorMessage(response: Response<*>): String {
        val raw = try {
            response.errorBody()?.string().orEmpty()
        } catch (_: Exception) {
            ""
        }
        if (raw.isNotBlank()) {
            try {
                val obj = JSONObject(raw)
                if (obj.has("detail")) {
                    val detail = obj.get("detail")
                    when (detail) {
                        is String -> if (detail.isNotBlank()) return detail
                        is JSONArray -> {
                            val msgs = buildList {
                                for (i in 0 until detail.length()) {
                                    val item = detail.optJSONObject(i)
                                    val msg = item?.optString("msg").orEmpty()
                                    if (msg.isNotBlank()) add(msg)
                                }
                            }
                            if (msgs.isNotEmpty()) return msgs.joinToString("; ")
                        }
                    }
                }
            } catch (_: Exception) {
                // Ошибка пришла не в JSON-формате.
            }
        }
        return "Ошибка сервера (${response.code()})"
    }
}
