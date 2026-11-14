package ru.cyber102.arinspector

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import ru.cyber102.arinspector.ui.theme.PromScanTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as PromScanApp).container
        setContent {
            PromScanTheme {
                PromScanRootApp(container = container)
            }
        }
    }
}
