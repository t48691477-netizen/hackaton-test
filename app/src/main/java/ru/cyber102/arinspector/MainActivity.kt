package ru.cyber102.arinspector

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.ui.ar.ArScreen
import ru.cyber102.arinspector.ui.scanner.ScannerScreen
import ru.cyber102.arinspector.ui.theme.ARInspectorTheme
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.vm.InspectionViewModel

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Отладочный вход в сцену без QR:
        //   adb shell am start -n ru.cyber102.arinspector/.MainActivity \
        //       --es equipment_id PUMP-402
        val presetEquipmentId: String? = intent?.getStringExtra(EXTRA_EQUIPMENT_ID)

        setContent {
            ARInspectorTheme {
                AppRoot(presetEquipmentId)
            }
        }
    }

    private companion object {
        const val EXTRA_EQUIPMENT_ID = "equipment_id"
    }
}

private sealed interface Screen {
    data object Scanner : Screen
    data class Ar(val equipment: Equipment) : Screen
}

@Composable
private fun AppRoot(presetEquipmentId: String?) {
    val vm: InspectionViewModel = viewModel()
    var screen by remember { mutableStateOf<Screen>(Screen.Scanner) }

    LaunchedEffect(presetEquipmentId) {
        if (!presetEquipmentId.isNullOrBlank()) vm.loadEquipment(presetEquipmentId)
    }

    BackHandler(enabled = screen is Screen.Ar) {
        vm.consumeEquipment()
        screen = Screen.Scanner
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack)
    ) {
        AnimatedContent(
            targetState = screen,
            transitionSpec = {
                fadeIn(tween(260)) togetherWith fadeOut(tween(180))
            },
            label = "screen"
        ) { current ->
            when (current) {
                is Screen.Scanner -> ScannerScreen(
                    vm = vm,
                    onEquipmentReady = { equipment -> screen = Screen.Ar(equipment) }
                )

                is Screen.Ar -> ArScreen(
                    vm = vm,
                    equipment = current.equipment,
                    onBack = {
                        vm.consumeEquipment()
                        screen = Screen.Scanner
                    }
                )
            }
        }
    }
}
