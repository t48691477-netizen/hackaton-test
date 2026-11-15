package ru.cyber102.arinspector.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "promscan_settings"
)

data class AppSettings(
    val serverUrl: String = SettingsStore.DEFAULT_SERVER_URL,
    val analysisIntervalMs: Long = SettingsStore.DEFAULT_INTERVAL_MS,
    val analysisIntervalSec: Int = (analysisIntervalMs / 1000L).toInt().coerceAtLeast(1)
)

class SettingsStore(context: Context) {

    private val dataStore = context.applicationContext.settingsDataStore
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    @Volatile
    var currentBaseUrl: String = DEFAULT_SERVER_URL
        private set

    @Volatile
    var currentIntervalMs: Long = DEFAULT_INTERVAL_MS
        private set

    @Volatile
    var currentIntervalSec: Int = 1
        private set

    val settingsFlow: Flow<AppSettings> = dataStore.data.map { prefs ->
        val url = normalizeUrl(prefs[KEY_SERVER_URL] ?: DEFAULT_SERVER_URL)
        val intervalMs = (prefs[KEY_INTERVAL_MS]?.toLong()
            ?: prefs[KEY_INTERVAL_SEC]?.let { it * 1000L }
            ?: DEFAULT_INTERVAL_MS).coerceIn(200L, 5000L)
        currentBaseUrl = url
        currentIntervalMs = intervalMs
        currentIntervalSec = (intervalMs / 1000L).toInt().coerceAtLeast(1)
        AppSettings(serverUrl = url, analysisIntervalMs = intervalMs, analysisIntervalSec = currentIntervalSec)
    }

    init {
        scope.launch {
            settingsFlow.collect { }
        }
    }

    suspend fun saveServerUrl(rawUrl: String): String {
        val normalized = normalizeUrl(rawUrl)
        currentBaseUrl = normalized
        dataStore.edit { prefs ->
            prefs[KEY_SERVER_URL] = normalized
        }
        return normalized
    }

    suspend fun saveAnalysisIntervalMs(ms: Long) {
        val clamped = ms.coerceIn(200L, 5000L)
        currentIntervalMs = clamped
        currentIntervalSec = (clamped / 1000L).toInt().coerceAtLeast(1)
        dataStore.edit { prefs ->
            prefs[KEY_INTERVAL_MS] = clamped.toInt()
            prefs[KEY_INTERVAL_SEC] = currentIntervalSec
        }
    }

    suspend fun saveAnalysisInterval(seconds: Int) {
        saveAnalysisIntervalMs(seconds * 1000L)
    }

    companion object {
        const val DEFAULT_SERVER_URL = "http://10.0.2.2:8000/"
        const val DEFAULT_INTERVAL_MS = 300L
        const val DEFAULT_INTERVAL_SEC = 1

        private val KEY_SERVER_URL = stringPreferencesKey("server_url")
        private val KEY_INTERVAL_MS = intPreferencesKey("analysis_interval_ms")
        private val KEY_INTERVAL_SEC = intPreferencesKey("analysis_interval_sec")

        fun normalizeUrl(raw: String): String {
            val trimmed = raw.trim()
            if (trimmed.isEmpty()) return DEFAULT_SERVER_URL
            val withScheme = if (trimmed.startsWith("http://", ignoreCase = true) ||
                trimmed.startsWith("https://", ignoreCase = true)
            ) {
                trimmed
            } else {
                "http://$trimmed"
            }
            return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
        }
    }
}
