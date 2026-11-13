package ru.cyber102.arinspector.data

import android.content.Context
import android.util.Base64
import android.util.Log
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.time.Instant
import java.util.concurrent.TimeUnit

class EquipmentRepository(
    context: Context,
    private val settings: AppSettings
) {

    private val gson = Gson()

    private val logInterceptor = Interceptor { chain ->
        val request = chain.request()
        val started = System.currentTimeMillis()
        val response: Response = chain.proceed(request)
        Log.d(
            "AR-Inspector",
            "${request.method} ${request.url.encodedPath} → ${response.code} " +
                "(${System.currentTimeMillis() - started} ms)"
        )
        response
    }

    private val okHttp = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(logInterceptor)
        .build()

    @Volatile
    private var retrofit: Retrofit? = null

    @Volatile
    private var retrofitBaseUrl: String? = null

    private fun api(): CyberApi {
        val baseUrl = settings.normalizedBaseUrl()
        synchronized(this) {
            val cached = retrofit
            if (cached == null || retrofitBaseUrl != baseUrl) {
                val built = Retrofit.Builder()
                    .baseUrl(baseUrl)
                    .client(okHttp)
                    .addConverterFactory(GsonConverterFactory.create(gson))
                    .build()
                retrofit = built
                retrofitBaseUrl = baseUrl
                return built.create(CyberApi::class.java)
            }
            return cached.create(CyberApi::class.java)
        }
    }

    suspend fun equipment(id: String): Fetched<Equipment> = withContext(Dispatchers.IO) {
        if (settings.demoMode) {
            return@withContext Fetched(DemoData.equipment(id), fromDemo = true)
        }
        runCatching { api().equipment(id) }
            .map { Fetched(it, fromDemo = false) }
            .getOrElse { Fetched(DemoData.equipment(id), fromDemo = true) }
    }

    suspend fun inspect(
        equipmentId: String,
        jpeg: ByteArray?,
        screenAspect: Float
    ): Fetched<InspectResponse> = withContext(Dispatchers.IO) {
        if (settings.demoMode) {
            return@withContext Fetched(DemoData.inspection(equipmentId), fromDemo = true)
        }
        val base64 = jpeg?.let { Base64.encodeToString(it, Base64.NO_WRAP) }
        val request = InspectRequest(
            equipmentId = equipmentId,
            imageBase64 = base64,
            screenAspect = screenAspect
        )
        runCatching { api().inspect(request) }
            .map { Fetched(it, fromDemo = false) }
            .getOrElse { Fetched(DemoData.inspection(equipmentId), fromDemo = true) }
    }

    suspend fun report(request: ReportRequest): Fetched<ReportResponse> =
        withContext(Dispatchers.IO) {
            if (settings.demoMode) {
                delay(700)
                return@withContext Fetched(mockReport(request), fromDemo = true)
            }
            runCatching { api().report(request) }
                .map { Fetched(it, fromDemo = false) }
                .getOrElse {
                    delay(350)
                    Fetched(mockReport(request), fromDemo = true)
                }
        }

    /** Статус сервера: mock или live (реальная vision/LLM-модель на бэкенде). */
    suspend fun health(): Fetched<HealthResponse> = withContext(Dispatchers.IO) {
        if (settings.demoMode) {
            return@withContext Fetched(HealthResponse("ok", "mock", "demo-data"), fromDemo = true)
        }
        runCatching { api().health() }
            .map { Fetched(it, fromDemo = false) }
            .getOrElse { Fetched(HealthResponse("offline", "mock", null), fromDemo = true) }
    }

    suspend fun chat(request: ChatRequest): Fetched<ChatResponse> = withContext(Dispatchers.IO) {
        if (settings.demoMode) {
            delay(550)
            return@withContext Fetched(ChatResponse(MottelScript.reply(request.message), "demo"), true)
        }
        runCatching { api().chat(request) }
            .map { Fetched(it, fromDemo = false) }
            .getOrElse {
                delay(300)
                Fetched(ChatResponse(MottelScript.reply(request.message), "offline"), true)
            }
    }

    private fun mockReport(request: ReportRequest): ReportResponse {
        val suffix = (System.currentTimeMillis() % 1_000_000).toString().padStart(6, '0')
        return ReportResponse(
            reportId = "ACT-$suffix",
            status = request.status,
            createdAt = Instant.now().toString()
        )
    }
}
