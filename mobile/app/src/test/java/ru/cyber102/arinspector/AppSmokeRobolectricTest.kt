package ru.cyber102.arinspector

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class AppSmokeRobolectricTest {

    @Test
    fun `app name matches PromScan`() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        assertEquals("ПромСкан", context.getString(R.string.app_name))
    }
}
