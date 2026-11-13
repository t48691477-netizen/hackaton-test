package ru.cyber102.arinspector.ui.scanner

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.cyber102.arinspector.data.DemoData
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.ui.components.HudPanel
import ru.cyber102.arinspector.ui.components.MonoLabel
import ru.cyber102.arinspector.ui.components.ScanLine
import ru.cyber102.arinspector.ui.components.StatusPill
import ru.cyber102.arinspector.ui.settings.SettingsSheet
import ru.cyber102.arinspector.ui.theme.HudBlack
import ru.cyber102.arinspector.ui.theme.HudCyan
import ru.cyber102.arinspector.ui.theme.HudGreen
import ru.cyber102.arinspector.ui.theme.HudLine
import ru.cyber102.arinspector.ui.theme.HudSurface
import ru.cyber102.arinspector.ui.theme.HudRed
import ru.cyber102.arinspector.ui.theme.SafetyYellow
import ru.cyber102.arinspector.ui.theme.TextDim
import ru.cyber102.arinspector.ui.theme.TextMuted
import ru.cyber102.arinspector.ui.theme.TextPrimary
import ru.cyber102.arinspector.vm.InspectionViewModel
import kotlin.math.min

@Composable
fun ScannerScreen(
    vm: InspectionViewModel,
    onEquipmentReady: (Equipment) -> Unit
) {
    val context = LocalContext.current
    val equipment by vm.equipment.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val demoMode by vm.demoMode.collectAsStateWithLifecycle()

    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    LaunchedEffect(equipment) {
        equipment?.let(onEquipmentReady)
    }

    var manualId by remember { mutableStateOf("") }
    var showSettings by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack)
    ) {
        if (hasPermission) {
            ScannerCamera(
                onQr = { raw -> if (!loading) vm.loadEquipment(raw) },
                modifier = Modifier.fillMaxSize()
            )
        } else {
            PermissionPlaceholder(
                onRequest = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                modifier = Modifier.fillMaxSize()
            )
        }

        // Затемнение сверху/снизу для читаемости HUD
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to HudBlack.copy(alpha = 0.92f),
                        0.28f to Color.Transparent,
                        0.55f to Color.Transparent,
                        1f to HudBlack.copy(alpha = 0.97f)
                    )
                )
        )

        if (hasPermission) {
            ScannerReticle(Modifier.fillMaxSize())
            ScanLine(
                modifier = Modifier.fillMaxSize(),
                color = HudCyan
            )
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(38.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(SafetyYellow.copy(alpha = 0.12f))
                        .border(1.dp, SafetyYellow.copy(alpha = 0.6f), RoundedCornerShape(8.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Filled.QrCodeScanner,
                        contentDescription = null,
                        tint = SafetyYellow,
                        modifier = Modifier.size(22.dp)
                    )
                }
                Spacer(Modifier.width(10.dp))
                Column {
                    Text(
                        text = "AR · ИНСПЕКТОР",
                        style = MaterialTheme.typography.titleLarge,
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                    MonoLabel("кибер 102 · обслуживание оборудования")
                }
                Spacer(Modifier.weight(1f))
                StatusPill(
                    text = if (demoMode) "DEMO" else "LIVE",
                    color = if (demoMode) HudCyan else HudGreen
                )
            }

            Spacer(Modifier.weight(1f))

            HudPanel(
                modifier = Modifier.fillMaxWidth(),
                accent = SafetyYellow
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        StatusPill("ML KIT · QR", HudCyan)
                        Spacer(Modifier.width(8.dp))
                        Spacer(Modifier.weight(1f))
                        MonoLabel("ШАГ 01 / 03")
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = "Наведите камеру на QR-код",
                        style = MaterialTheme.typography.titleLarge,
                        color = TextPrimary
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = "Код оборудования откроет AR-схему узлов и ИИ-инспекцию.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextMuted
                    )
                    Spacer(Modifier.height(12.dp))

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        DemoData.demoIds.forEach { id ->
                            DemoChip(
                                id = id,
                                onClick = { if (!loading) vm.loadEquipment(id) }
                            )
                        }
                    }

                    Spacer(Modifier.height(12.dp))

                    OutlinedTextField(
                        value = manualId,
                        onValueChange = { manualId = it.uppercase() },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = {
                            Text(
                                "или введите код вручную: PUMP-402",
                                color = TextDim,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        },
                        singleLine = true,
                        textStyle = MaterialTheme.typography.bodyLarge.copy(
                            fontFamily = FontFamily.Monospace,
                            color = TextPrimary
                        ),
                        trailingIcon = {
                            IconButton(
                                onClick = {
                                    if (manualId.isNotBlank() && !loading) vm.loadEquipment(manualId)
                                }
                            ) {
                                Icon(
                                    Icons.Filled.ArrowForward,
                                    contentDescription = "Открыть",
                                    tint = SafetyYellow
                                )
                            }
                        },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                        keyboardActions = KeyboardActions(
                            onGo = {
                                if (manualId.isNotBlank() && !loading) vm.loadEquipment(manualId)
                            }
                        ),
                        shape = RoundedCornerShape(8.dp)
                    )

                    Spacer(Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Switch(
                            checked = demoMode,
                            onCheckedChange = { vm.setDemoMode(it) },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = HudBlack,
                                checkedTrackColor = SafetyYellow,
                                uncheckedThumbColor = TextMuted,
                                uncheckedTrackColor = HudLine
                            )
                        )
                        Spacer(Modifier.width(8.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                text = "Демо-режим",
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary
                            )
                            MonoLabel("локальные ответы API · офлайн")
                        }
                        TextButton(onClick = { showSettings = true }) {
                            Icon(
                                Icons.Filled.Settings,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = HudCyan
                            )
                            Spacer(Modifier.width(4.dp))
                            Text("Сеть", color = HudCyan)
                        }
                    }

                    error?.let {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = HudRed
                        )
                    }
                }
            }
        }

        if (loading) {
            LoadingOverlay()
        }
    }

    if (showSettings) {
        SettingsSheet(vm = vm, onDismiss = { showSettings = false })
    }
}

@Composable
private fun DemoChip(id: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(HudSurface)
            .border(1.dp, HudLine, RoundedCornerShape(6.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(
            text = id,
            style = MaterialTheme.typography.labelSmall,
            fontFamily = FontFamily.Monospace,
            color = HudCyan
        )
    }
}

@Composable
private fun LoadingOverlay() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack.copy(alpha = 0.82f)),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = SafetyYellow)
            Spacer(Modifier.height(16.dp))
            Text(
                text = "GET /api/equipment/…",
                style = MaterialTheme.typography.labelMedium,
                color = SafetyYellow
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Запрашиваем схему узлов",
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted
            )
        }
    }
}

@Composable
private fun PermissionPlaceholder(onRequest: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .background(HudBlack)
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Filled.CameraAlt,
                contentDescription = null,
                tint = SafetyYellow,
                modifier = Modifier.size(44.dp)
            )
            Spacer(Modifier.height(14.dp))
            Text(
                text = "Нужен доступ к камере",
                style = MaterialTheme.typography.titleLarge,
                color = TextPrimary
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Сканирование QR и AR-инспекция работают только с камерой.",
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted,
                textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(16.dp))
            TextButton(onClick = onRequest) {
                Text("Разрешить", color = SafetyYellow, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun ScannerReticle(modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "reticle")
    val progress by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "reticle-progress"
    )

    Canvas(modifier = modifier) {
        val box = min(size.width * 0.68f, 300.dp.toPx())
        val left = (size.width - box) / 2f
        val top = (size.height - box) / 2f - 40.dp.toPx()
        val scrim = Color.Black.copy(alpha = 0.32f)

        drawRect(scrim, size = Size(size.width, top.coerceAtLeast(0f)))
        drawRect(
            scrim,
            topLeft = Offset(0f, top + box),
            size = Size(size.width, (size.height - top - box).coerceAtLeast(0f))
        )
        drawRect(scrim, topLeft = Offset(0f, top), size = Size(left, box))
        drawRect(
            scrim,
            topLeft = Offset(left + box, top),
            size = Size((size.width - left - box).coerceAtLeast(0f), box)
        )

        val bracket = 30.dp.toPx()
        val stroke = 3.dp.toPx()
        drawLine(SafetyYellow, Offset(left, top), Offset(left + bracket, top), stroke)
        drawLine(SafetyYellow, Offset(left, top), Offset(left, top + bracket), stroke)
        drawLine(SafetyYellow, Offset(left + box, top), Offset(left + box - bracket, top), stroke)
        drawLine(SafetyYellow, Offset(left + box, top), Offset(left + box, top + bracket), stroke)
        drawLine(SafetyYellow, Offset(left, top + box), Offset(left + bracket, top + box), stroke)
        drawLine(SafetyYellow, Offset(left, top + box), Offset(left, top + box - bracket), stroke)
        drawLine(SafetyYellow, Offset(left + box, top + box), Offset(left + box - bracket, top + box), stroke)
        drawLine(SafetyYellow, Offset(left + box, top + box), Offset(left + box, top + box - bracket), stroke)

        val y = top + box * progress
        drawLine(
            color = SafetyYellow.copy(alpha = 0.85f),
            start = Offset(left + 6.dp.toPx(), y),
            end = Offset(left + box - 6.dp.toPx(), y),
            strokeWidth = 1.5.dp.toPx()
        )
    }
}

@Composable
private fun ScannerCamera(onQr: (String) -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
    }
    var handled by remember { mutableStateOf(false) }
    val analyzer = remember {
        QrAnalyzer { raw ->
            if (!handled) {
                handled = true
                onQr(raw)
            }
        }
    }

    DisposableEffect(Unit) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        val executor = ContextCompat.getMainExecutor(context)
        providerFuture.addListener({
            runCatching {
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { it.setAnalyzer(executor, analyzer) }
                provider.unbindAll()
                runCatching {
                    provider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        analysis
                    )
                }.onFailure {
                    runCatching {
                        provider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_FRONT_CAMERA,
                            preview,
                            analysis
                        )
                    }
                }
            }
        }, executor)
        onDispose {
            runCatching { providerFuture.get().unbindAll() }
            analyzer.close()
        }
    }

    AndroidView(factory = { previewView }, modifier = modifier)
}
