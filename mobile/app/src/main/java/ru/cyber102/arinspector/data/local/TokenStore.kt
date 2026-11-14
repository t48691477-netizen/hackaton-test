package ru.cyber102.arinspector.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class TokenStore(context: Context) {

    private val prefs: SharedPreferences = createEncryptedPrefs(context.applicationContext)

    @Volatile
    private var cachedToken: String? = prefs.getString(KEY_SESSION_TOKEN, null)

    private val _tokenFlow = MutableStateFlow(cachedToken)
    val tokenFlow: StateFlow<String?> = _tokenFlow.asStateFlow()

    fun getToken(): String? = cachedToken

    fun saveToken(token: String) {
        cachedToken = token
        _tokenFlow.value = token
        prefs.edit().putString(KEY_SESSION_TOKEN, token).apply()
    }

    fun clearToken() {
        cachedToken = null
        _tokenFlow.value = null
        prefs.edit().remove(KEY_SESSION_TOKEN).apply()
    }

    private fun createEncryptedPrefs(context: Context): SharedPreferences {
        return try {
            buildEncryptedPrefs(context)
        } catch (_: Exception) {
            // При повреждении мастер-ключа после переустановки сбрасываем и пробуем пересоздать.
            context.deleteSharedPreferences(PREFS_NAME)
            try {
                buildEncryptedPrefs(context)
            } catch (_: Exception) {
                // Резервный вариант для тестовых сред (Robolectric) без AndroidKeyStore.
                context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            }
        }
    }

    private fun buildEncryptedPrefs(context: Context): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        return EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    private companion object {
        const val PREFS_NAME = "promscan_secure_prefs"
        const val KEY_SESSION_TOKEN = "session_token"
    }
}
