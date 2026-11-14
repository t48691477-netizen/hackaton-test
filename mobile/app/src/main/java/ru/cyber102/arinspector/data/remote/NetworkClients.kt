package ru.cyber102.arinspector.data.remote

import android.content.Context
import coil.ImageLoader
import com.squareup.moshi.Moshi
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import ru.cyber102.arinspector.data.local.SettingsStore
import ru.cyber102.arinspector.data.local.TokenStore
import java.util.concurrent.TimeUnit

/**
 * Подменяет схему, хост, порт и базовый префикс пути каждого запроса на актуальный URL из SettingsStore,
 * чтобы смена адреса сервера применялась мгновенно без пересоздания Retrofit.
 */
class BaseUrlInterceptor(
    private val settingsStore: SettingsStore
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val originalUrl = originalRequest.url
        val targetBase = settingsStore.currentBaseUrl.toHttpUrlOrNull()

        if (targetBase == null) {
            return chain.proceed(originalRequest)
        }

        val isPlaceholderHost = originalUrl.host == PLACEHOLDER_HOST
        val newUrl = if (isPlaceholderHost) {
            val baseSegments = targetBase.encodedPathSegments.filter { it.isNotEmpty() }
            val reqSegments = originalUrl.encodedPathSegments.filter { it.isNotEmpty() }
            val builder = originalUrl.newBuilder()
                .scheme(targetBase.scheme)
                .host(targetBase.host)
                .port(targetBase.port)
                .encodedPath("/")
            baseSegments.forEach { builder.addEncodedPathSegment(it) }
            reqSegments.forEach { builder.addEncodedPathSegment(it) }
            builder.build()
        } else {
            originalUrl
        }

        val updatedRequest = originalRequest.newBuilder()
            .url(newUrl)
            .build()
        return chain.proceed(updatedRequest)
    }

    companion object {
        const val PLACEHOLDER_HOST = "promscan.local"
        const val PLACEHOLDER_BASE_URL = "http://$PLACEHOLDER_HOST/"
    }
}

class AuthInterceptor(
    private val tokenStore: TokenStore
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenStore.getToken()
        val request = if (!token.isNullOrBlank()) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

object NetworkFactory {

    fun createMoshi(): Moshi = Moshi.Builder().build()

    fun createOkHttpClient(
        settingsStore: SettingsStore,
        tokenStore: TokenStore
    ): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        return OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .addInterceptor(BaseUrlInterceptor(settingsStore))
            .addInterceptor(AuthInterceptor(tokenStore))
            .addInterceptor(logging)
            .build()
    }

    fun createApi(okHttpClient: OkHttpClient, moshi: Moshi): PromScanApi {
        return Retrofit.Builder()
            .baseUrl(BaseUrlInterceptor.PLACEHOLDER_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(PromScanApi::class.java)
    }

    fun createImageLoader(context: Context, okHttpClient: OkHttpClient): ImageLoader {
        return ImageLoader.Builder(context.applicationContext)
            .okHttpClient(okHttpClient)
            .crossfade(true)
            .build()
    }
}
