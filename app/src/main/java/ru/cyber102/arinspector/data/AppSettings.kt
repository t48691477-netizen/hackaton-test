package ru.cyber102.arinspector.data

import android.content.Context
import ru.cyber102.arinspector.BuildConfig

class AppSettings(context: Context) {

    private val prefs =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Демо-режим включён по умолчанию — питч не должен зависеть от сети. */
    var demoMode: Boolean
        get() = prefs.getBoolean(KEY_DEMO, true)
        set(value) = prefs.edit().putBoolean(KEY_DEMO, value).apply()

    var baseUrl: String
        get() = prefs.getString(KEY_BASE_URL, BuildConfig.BASE_URL) ?: BuildConfig.BASE_URL
        set(value) = prefs.edit().putString(KEY_BASE_URL, value.trim()).apply()

    fun normalizedBaseUrl(): String {
        val url = baseUrl.trim().ifEmpty { BuildConfig.BASE_URL }
        return if (url.endsWith("/")) url else "$url/"
    }

    private companion object {
        const val PREFS = "ar_inspector_settings"
        const val KEY_DEMO = "demo_mode"
        const val KEY_BASE_URL = "base_url"
    }
}
