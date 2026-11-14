package ru.cyber102.arinspector

import android.content.Context
import coil.ImageLoader
import com.squareup.moshi.Moshi
import okhttp3.OkHttpClient
import ru.cyber102.arinspector.data.local.SettingsStore
import ru.cyber102.arinspector.data.local.TokenStore
import ru.cyber102.arinspector.data.remote.NetworkFactory
import ru.cyber102.arinspector.data.remote.PromScanApi
import ru.cyber102.arinspector.data.repository.PromScanRepository

class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    val settingsStore = SettingsStore(appContext)
    val tokenStore = TokenStore(appContext)
    val moshi: Moshi = NetworkFactory.createMoshi()
    val okHttpClient: OkHttpClient = NetworkFactory.createOkHttpClient(settingsStore, tokenStore)
    val api: PromScanApi = NetworkFactory.createApi(okHttpClient, moshi)
    val imageLoader: ImageLoader = NetworkFactory.createImageLoader(appContext, okHttpClient)
    val repository = PromScanRepository(
        api = api,
        moshi = moshi,
        tokenStore = tokenStore,
        settingsStore = settingsStore
    )
}
