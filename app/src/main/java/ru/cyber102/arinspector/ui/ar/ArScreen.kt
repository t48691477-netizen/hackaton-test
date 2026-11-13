package ru.cyber102.arinspector.ui.ar

import android.view.MotionEvent
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
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
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CenterFocusStrong
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.ar.core.Anchor
import com.google.ar.core.ArCoreApk
import com.google.ar.core.Config
import com.google.ar.core.Frame
import com.google.ar.core.Pose
import com.google.ar.core.Session
import io.github.sceneview.ar.ARScene
import io.github.sceneview.ar.arcore.createAnchorOrNull
import io.github.sceneview.ar.arcore.isValid
import io.github.sceneview.ar.node.AnchorNode
import io.github.sceneview.ar.rememberARCameraNode
import io.github.sceneview.loaders.MaterialLoader
import io.github.sceneview.math.Direction
import io.github.sceneview.math.Position
import io.github.sceneview.math.Size
import io.github.sceneview.node.ImageNode
import io.github.sceneview.node.Node
import io.github.sceneview.node.SphereNode
import io.github.sceneview.rememberEngine
import io.github.sceneview.rememberMaterialLoader
import io.github.sceneview.rememberModelLoader
import io.github.sceneview.rememberNodes
import io.github.sceneview.rememberOnGestureListener
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.data.EquipmentComponent
import ru.cyber102.arinspector.data.InspectResponse
import ru.cyber102.arinspector.ui.assistant.AssistantSheet
import ru.cyber102.arinspector.ui.components.HudPanel
import ru.cyber102.arinspector.ui.components.MonoLabel
import ru.cyber102.arinspector.ui.components.MottelBadge
import ru.cyber102.arinspector.ui.components.StatusPill
import ru.cyber102.arinspector.ui.components.ThumbAction
import ru.cyber102.arinspector.ui.result.ResultSheet
import ru.cyber102.arinspector.ui.theme.HudAmber
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
import ru.cyber102.arinspector.util.ImageUtils
import ru.cyber102.arinspector.vm.InspectionViewModel
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

class ArController {
    internal var placeAtCenter: (() -> Unit)? = null
    internal var capture: (() -> Unit)? = null

    fun place() {
        placeAtCenter?.invoke()
    }

    fun scan() {
        capture?.invoke()
    }
}

object ArCoreSupport {
    fun isSupported(context: android.content.Context): Boolean {
        return when (ArCoreApk.getInstance().checkAvailability(context)) {
            ArCoreApk.Availability.SUPPORTED_INSTALLED,
            ArCoreApk.Availability.SUPPORTED_NOT_INSTALLED,
            ArCoreApk.Availability.SUPPORTED_APK_TOO_OLD -> true

            else -> false
        }
    }
}

@Composable
fun ArScreen(
    vm: InspectionViewModel,
    equipment: Equipment,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val inspection by vm.inspection.collectAsStateWithLifecycle()
    val scanning by vm.scanning.collectAsStateWithLifecycle()
    val demoResponse by vm.demoResponse.collectAsStateWithLifecycle()
    val haptic = LocalHapticFeedback.current

    var arSupported by remember { mutableStateOf<Boolean?>(null) }
    var arFailed by remember { mutableStateOf(false) }
    var anchorPlaced by remember { mutableStateOf(false) }
    var selectedComponent by remember { mutableStateOf<EquipmentComponent?>(null) }
    var selectedDefect by remember { mutableStateOf<Defect?>(null) }
    val controller = remember { ArController() }
    val assistantOpen by vm.assistantOpen.collectAsStateWithLifecycle()
    val serverHealth by vm.serverHealth.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        arSupported = withContext(Dispatchers.IO) { ArCoreSupport.isSupported(context) }
        vm.refreshHealth()
    }

    LaunchedEffect(inspection) {
        if (inspection?.isCritical == true) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        }
    }

    val stageModifier = Modifier.fillMaxSize()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack)
    ) {
        when {
            arSupported == null -> ArLoading()
            arSupported == true && !arFailed -> ArCoreStage(
                vm = vm,
                equipment = equipment,
                inspection = inspection,
                controller = controller,
                modifier = stageModifier,
                onNodeSelected = { component ->
                    selectedDefect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
                    selectedComponent = component
                },
                onAnchorChanged = { anchorPlaced = it },
                onFallback = { arFailed = true }
            )

            else -> FallbackStage(
                vm = vm,
                equipment = equipment,
                inspection = inspection,
                controller = controller,
                modifier = stageModifier,
                onNodeSelected = { component ->
                    selectedDefect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
                    selectedComponent = component
                },
                onDefectTap = { defect ->
                    selectedDefect = defect
                    selectedComponent = resolveComponent(equipment, defect)
                        ?: syntheticComponent(defect)
                }
            )
        }

        if (inspection?.defects?.isNotEmpty() == true &&
            arSupported == true && !arFailed
        ) {
            // В настоящем AR оверлей лежит поверх SceneView и перехватывает тапы:
            // выбор узла там дублируется чипами в нижней панели.
            DefectOverlay(
                defects = inspection?.defects.orEmpty(),
                modifier = Modifier.fillMaxSize(),
                onDefectTap = { defect ->
                    selectedDefect = defect
                    selectedComponent = resolveComponent(equipment, defect)
                        ?: syntheticComponent(defect)
                }
            )
        }

        if (scanning) {
            ScanningOverlay()
        }

        ArTopBar(
            equipment = equipment,
            demoResponse = demoResponse,
            fallback = arSupported == false || arFailed,
            health = serverHealth,
            onBack = onBack
        )

        ArBottomBar(
            equipment = equipment,
            inspection = inspection,
            scanning = scanning,
            anchorPlaced = anchorPlaced,
            fallback = arSupported == false || arFailed,
            assistantBusy = false,
            onPlaceAnchor = { controller.place() },
            onScan = { controller.scan() },
            onAssistant = { vm.openAssistant() },
            onNodeSelected = { component ->
                selectedDefect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
                selectedComponent = component
            },
            modifier = Modifier
                .align(Alignment.BottomCenter)
        )
    }

    if (assistantOpen) {
        AssistantSheet(vm = vm, onDismiss = { vm.closeAssistant() })
    }

    val component = selectedComponent
    if (component != null) {
        ResultSheet(
            equipment = equipment,
            component = component,
            defect = selectedDefect,
            inspection = inspection,
            vm = vm,
            onDismiss = {
                selectedComponent = null
                selectedDefect = null
            }
        )
    }
}

private fun resolveComponent(
    equipment: Equipment,
    defect: Defect
): EquipmentComponent? {
    equipment.components.firstOrNull { it.id == defect.nodeId }?.let { return it }
    val offset = defect.offsetFromQr ?: return null
    return equipment.components.minByOrNull { component ->
        val dx = component.offsetFromQr.x - offset.x
        val dy = component.offsetFromQr.y - offset.y
        val dz = component.offsetFromQr.z - offset.z
        dx * dx + dy * dy + dz * dz
    }?.takeIf { component ->
        val dx = component.offsetFromQr.x - offset.x
        val dy = component.offsetFromQr.y - offset.y
        val dz = component.offsetFromQr.z - offset.z
        kotlin.math.sqrt(dx * dx + dy * dy + dz * dz) <= component.radius
    }
}

private fun syntheticComponent(defect: Defect) = EquipmentComponent(
    id = defect.nodeId ?: "—",
    name = defect.displayTitle,
    description = "Дефект вне привязки к узлу"
)

@Composable
private fun ArCoreStage(
    vm: InspectionViewModel,
    equipment: Equipment,
    inspection: InspectResponse?,
    controller: ArController,
    modifier: Modifier = Modifier,
    onNodeSelected: (EquipmentComponent) -> Unit,
    onAnchorChanged: (Boolean) -> Unit,
    onFallback: () -> Unit
) {
    val engine = rememberEngine()
    val modelLoader = rememberModelLoader(engine)
    val materialLoader = rememberMaterialLoader(engine)
    val cameraNode = rememberARCameraNode(engine)
    val childNodes = rememberNodes()

    var anchorNode by remember { mutableStateOf<AnchorNode?>(null) }
    val plates = remember { mutableListOf<Node>() }

    val pendingCapture = remember { AtomicBoolean(false) }
    val pendingPlace = remember { AtomicReference<Offset?>(null) }

    val configuration = LocalConfiguration.current
    val density = LocalDensity.current
    val screenAspect = configuration.screenWidthDp.toFloat() /
        configuration.screenHeightDp.toFloat().coerceAtLeast(1f)
    val screenWidthPx = with(density) { configuration.screenWidthDp.dp.toPx() }
    val screenHeightPx = with(density) { configuration.screenHeightDp.dp.toPx() }

    fun destroyMarkers(parent: AnchorNode) {
        synchronized(plates) {
            parent.childNodes.toList().forEach { it.destroy() }
            parent.clearChildNodes()
            plates.clear()
        }
    }

    fun rebuildMarkers(parent: AnchorNode) {
        destroyMarkers(parent)
        equipment.components.forEach { component ->
            val defect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
            val critical = defect != null && (defect.isCritical || inspection.isCritical)
            val accent = when {
                critical -> HudRed
                defect != null -> SafetyYellow
                else -> HudCyan
            }
            val pos = Position(
                component.offsetFromQr.x,
                component.offsetFromQr.y,
                component.offsetFromQr.z
            )

            val halo = SphereNode(
                engine = engine,
                radius = if (critical) 0.062f else 0.052f,
                materialInstance = materialLoader.createColorInstance(accent.copy(alpha = 0.20f))
            ).apply {
                name = "cmp:${component.id}"
                position = pos
                onSingleTapConfirmed = {
                    onNodeSelected(component)
                    true
                }
            }
            parent.addChildNode(halo)

            val sphere = SphereNode(
                engine = engine,
                radius = if (critical) 0.030f else 0.024f,
                materialInstance = materialLoader.createColorInstance(accent)
            ).apply {
                name = "cmp:${component.id}"
                position = pos
                onSingleTapConfirmed = {
                    onNodeSelected(component)
                    true
                }
            }
            parent.addChildNode(sphere)

            val plate = ImageNode(
                materialLoader = materialLoader,
                bitmap = MarkerBitmaps.label(
                    text = component.name.uppercase(),
                    accent = accent.toArgb(),
                    critical = critical
                ),
                size = Size(0.30f, 0.075f, 0f),
                normal = Direction(z = -1f)
            ).apply {
                name = "cmp:${component.id}"
                position = Position(pos.x, pos.y + 0.10f, pos.z)
                onSingleTapConfirmed = {
                    onNodeSelected(component)
                    true
                }
            }
            parent.addChildNode(plate)
            synchronized(plates) { plates += plate }
        }

        val basePlate = ImageNode(
            materialLoader = materialLoader,
            bitmap = MarkerBitmaps.label(
                text = "БАЗА QR",
                accent = HudCyan.toArgb(),
                critical = false
            ),
            size = Size(0.22f, 0.055f, 0f),
            normal = Direction(z = -1f)
        ).apply {
            position = Position(0f, 0.05f, 0f)
        }
        parent.addChildNode(basePlate)
        synchronized(plates) { plates += basePlate }
    }

    fun placeAnchor(anchor: Anchor) {
        if (anchorNode != null) return
        val node = AnchorNode(engine = engine, anchor = anchor)
        anchorNode = node
        childNodes += node
        rebuildMarkers(node)
        onAnchorChanged(true)
    }

    fun placeAt(session: Session, frame: Frame, x: Float, y: Float) {
        val hit = frame.hitTest(x, y).firstOrNull {
            it.isValid(depthPoint = false, point = false)
        }
        val anchor = hit?.createAnchorOrNull() ?: runCatching {
            session.createAnchor(
                frame.camera.pose.compose(Pose.makeTranslation(0f, 0f, -1f))
            )
        }.getOrNull() ?: return
        placeAnchor(anchor)
    }

    LaunchedEffect(inspection, anchorNode) {
        anchorNode?.let { rebuildMarkers(it) }
    }

    SideEffect {
        controller.placeAtCenter = {
            pendingPlace.set(Offset(screenWidthPx / 2f, screenHeightPx / 2f))
        }
        controller.capture = {
            pendingCapture.set(true)
        }
    }

    ARScene(
        modifier = modifier,
        engine = engine,
        modelLoader = modelLoader,
        materialLoader = materialLoader,
        cameraNode = cameraNode,
        childNodes = childNodes,
        planeRenderer = true,
        sessionConfiguration = { session, config ->
            config.planeFindingMode = Config.PlaneFindingMode.HORIZONTAL_AND_VERTICAL
            config.lightEstimationMode = Config.LightEstimationMode.ENVIRONMENTAL_HDR
            config.focusMode = Config.FocusMode.AUTO
            if (session.isDepthModeSupported(Config.DepthMode.AUTOMATIC)) {
                config.depthMode = Config.DepthMode.AUTOMATIC
            }
        },
        onSessionUpdated = { session, frame ->
            pendingPlace.getAndSet(null)?.let { point ->
                if (anchorNode == null) placeAt(session, frame, point.x, point.y)
            }

            if (pendingCapture.getAndSet(false)) {
                val image = runCatching { frame.acquireCameraImage() }.getOrNull()
                val yuv = image?.let { mediaImage ->
                    runCatching { ImageUtils.toYuvFrame(mediaImage) }
                        .also { mediaImage.close() }
                        .getOrNull()
                }
                vm.inspectWithYuv(equipment.id, yuv, 90, screenAspect)
            }

            if (anchorNode != null) {
                synchronized(plates) {
                    plates.forEach { plate ->
                        runCatching { plate.lookAt(cameraNode) }
                    }
                }
            }
        },
        onSessionFailed = {
            onFallback()
        },
        onGestureListener = rememberOnGestureListener(
            onSingleTapConfirmed = { event: MotionEvent, node: Node? ->
                val componentId = findComponentId(node)
                if (componentId != null) {
                    equipment.components.firstOrNull { it.id == componentId }
                        ?.let(onNodeSelected)
                } else if (anchorNode == null) {
                    pendingPlace.set(Offset(event.x, event.y))
                }
            }
        )
    )
}

private fun findComponentId(node: Node?): String? {
    var current = node
    while (current != null) {
        current.name?.let { name ->
            if (name.startsWith("cmp:")) return name.removePrefix("cmp:")
        }
        current = current.parent
    }
    return null
}

@Composable
private fun ArTopBar(
    equipment: Equipment,
    demoResponse: Boolean,
    fallback: Boolean,
    health: ru.cyber102.arinspector.data.HealthResponse?,
    onBack: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(HudBlack.copy(alpha = 0.92f), Color.Transparent)
                )
            )
            .statusBarsPadding()
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "Назад", tint = TextPrimary)
            }
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    MonoLabel("${equipment.id} · AR-СЦЕНА", color = SafetyYellow)
                    Spacer(Modifier.width(8.dp))
                    if (health?.isLive == true) {
                        StatusPill("LIVE AI", HudGreen)
                    } else if (demoResponse) {
                        StatusPill("DEMO", HudCyan)
                    }
                    if (fallback) {
                        Spacer(Modifier.width(6.dp))
                        StatusPill("SIM AR", HudAmber)
                    }
                }
                Text(
                    text = equipment.name,
                    style = MaterialTheme.typography.titleLarge,
                    color = TextPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                equipment.location?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.labelSmall,
                        color = TextMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

@Composable
private fun ArBottomBar(
    equipment: Equipment,
    inspection: InspectResponse?,
    scanning: Boolean,
    anchorPlaced: Boolean,
    fallback: Boolean,
    assistantBusy: Boolean,
    onPlaceAnchor: () -> Unit,
    onScan: () -> Unit,
    onAssistant: () -> Unit,
    onNodeSelected: (EquipmentComponent) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(Color.Transparent, HudBlack.copy(alpha = 0.95f))
                )
            )
            .navigationBarsPadding()
            .padding(start = 16.dp, end = 12.dp, top = 8.dp, bottom = 10.dp)
    ) {
        // Компактная сводка: цветная полоса + крупный текст статуса.
        inspection?.let { result ->
            val accent = when {
                result.isCritical -> HudRed
                result.defectCount > 0 -> SafetyYellow
                else -> HudGreen
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(4.dp))
                    .background(HudBlack.copy(alpha = 0.82f))
                    .border(1.dp, accent.copy(alpha = 0.45f), RoundedCornerShape(4.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(width = 3.dp, height = 30.dp)
                        .background(accent)
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        text = when {
                            result.defectCount == 0 -> "НОРМА · дефектов нет"
                            result.isCritical -> "КРИТИЧНО · ${result.defectCount} находки"
                            else -> "ВНИМАНИЕ · ${result.defectCount}"
                        },
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        maxLines = 1
                    )
                    MonoLabel("${result.model ?: "vision"} · нажми маркер для разбора")
                }
            }
            Spacer(Modifier.height(8.dp))
        }

        if (!anchorPlaced && !fallback) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(4.dp))
                    .background(HudBlack.copy(alpha = 0.72f))
                    .border(1.dp, HudCyan.copy(alpha = 0.4f), RoundedCornerShape(4.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Filled.CenterFocusStrong,
                    contentDescription = null,
                    tint = HudCyan,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "Якорь: наведи или",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextMuted,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    text = "РАЗМЕСТИТЬ",
                    style = MaterialTheme.typography.labelSmall,
                    color = SafetyYellow,
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .clickable { onPlaceAnchor() }
                        .padding(horizontal = 8.dp, vertical = 6.dp)
                )
            }
            Spacer(Modifier.height(8.dp))
        }

        // Полоса узлов: горизонтальный скролл, тап = карточка.
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            equipment.components.forEach { component ->
                val defect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
                val critical = defect != null && (defect.isCritical || inspection.isCritical)
                val accent = when {
                    critical -> HudRed
                    defect != null -> SafetyYellow
                    else -> HudCyan
                }
                Row(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(HudBlack.copy(alpha = 0.86f))
                        .border(1.dp, accent.copy(alpha = 0.5f), RoundedCornerShape(4.dp))
                        .clickable { onNodeSelected(component) }
                        .padding(start = 4.dp, end = 10.dp, top = 10.dp, bottom = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        Modifier
                            .size(width = 3.dp, height = 14.dp)
                            .background(accent)
                    )
                    Spacer(Modifier.width(7.dp))
                    Text(
                        text = component.name,
                        style = MaterialTheme.typography.labelSmall,
                        color = TextPrimary,
                        maxLines = 1
                    )
                }
            }
        }

        Spacer(Modifier.height(10.dp))

        // Главное действие — в правой нижней дуге большого пальца.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.Bottom
        ) {
            Column(
                modifier = Modifier.weight(1f),
                horizontalAlignment = Alignment.Start
            ) {
                MonoLabel(
                    text = if (inspection == null) "шаг 02 / 03 · осмотр" else "осмотр завершён",
                    color = TextDim
                )
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                MottelBadge(
                    modifier = Modifier
                        .clip(CircleShape)
                        .clickable { onAssistant() },
                    size = 46.dp,
                    speaking = assistantBusy
                )
                MonoLabel("моттэл", color = SafetyYellow)
            }

            Spacer(Modifier.width(14.dp))

            ThumbAction(
                label = when {
                    scanning -> "…"
                    inspection == null -> "СКАН"
                    else -> "ЕЩЁ"
                },
                caption = when {
                    scanning -> "анализ"
                    inspection == null -> "ии-осмотр"
                    else -> "сканировать"
                },
                accent = SafetyYellow,
                enabled = !scanning,
                onClick = onScan
            )
        }
    }
}

@Composable
private fun ScanningOverlay() {
    val transition = rememberInfiniteTransition(label = "ai-scan")
    val pulse by transition.animateFloat(
        initialValue = 0.2f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scan-pulse"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack.copy(alpha = 0.45f)),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(contentAlignment = Alignment.Center) {
                Box(
                    Modifier
                        .size(120.dp)
                        .border(1.dp, HudCyan.copy(alpha = pulse), CircleShape)
                )
                Box(
                    Modifier
                        .size(80.dp)
                        .border(1.dp, HudCyan.copy(alpha = pulse * 0.8f), CircleShape)
                )
                CircularProgressIndicator(
                    modifier = Modifier.size(34.dp),
                    color = SafetyYellow,
                    strokeWidth = 2.dp
                )
            }
            Spacer(Modifier.height(16.dp))
            Text(
                text = "ИИ-СКАНИРОВАНИЕ",
                style = MaterialTheme.typography.labelMedium,
                color = SafetyYellow,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(4.dp))
            MonoLabel("POST /api/inspect · анализ кадра")
        }
    }
}

@Composable
private fun FallbackStage(
    vm: InspectionViewModel,
    equipment: Equipment,
    inspection: InspectResponse?,
    controller: ArController,
    modifier: Modifier = Modifier,
    onNodeSelected: (EquipmentComponent) -> Unit,
    onDefectTap: (Defect) -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
    }
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()
    }
    val configuration = LocalConfiguration.current
    val screenAspect = configuration.screenWidthDp.toFloat() /
        configuration.screenHeightDp.toFloat().coerceAtLeast(1f)

    DisposableEffect(Unit) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        val executor = ContextCompat.getMainExecutor(context)
        providerFuture.addListener({
            runCatching {
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
                provider.unbindAll()
                runCatching {
                    provider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageCapture
                    )
                }.onFailure {
                    runCatching {
                        provider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_FRONT_CAMERA,
                            preview,
                            imageCapture
                        )
                    }
                }
            }
        }, executor)
        onDispose {
            runCatching { providerFuture.get().unbindAll() }
        }
    }

    SideEffect {
        controller.placeAtCenter = { /* в fallback-режиме якорь уже в центре */ }
        controller.capture = {
            imageCapture.takePicture(
                ContextCompat.getMainExecutor(context),
                object : ImageCapture.OnImageCapturedCallback() {
                    override fun onCaptureSuccess(image: ImageProxy) {
                        val buffer = image.planes[0].buffer
                        val bytes = ByteArray(buffer.remaining()).also { buffer.get(it) }
                        val rotation = image.imageInfo.rotationDegrees
                        image.close()
                        vm.inspectWithJpeg(equipment.id, bytes, rotation, screenAspect)
                    }

                    override fun onError(exception: ImageCaptureException) {
                        vm.inspectWithYuv(equipment.id, null, 0, screenAspect)
                    }
                }
            )
        }
    }

    Box(modifier = modifier) {
        AndroidView(factory = { previewView }, modifier = Modifier.fillMaxSize())
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to HudBlack.copy(alpha = 0.55f),
                        0.45f to Color.Transparent,
                        1f to HudBlack.copy(alpha = 0.72f)
                    )
                )
        )
        // Оверлей дефектов рисуется до маркеров и не перекрывает их тапы.
        if (inspection?.defects?.isNotEmpty() == true) {
            DefectOverlay(
                defects = inspection.defects,
                modifier = Modifier.fillMaxSize(),
                onDefectTap = onDefectTap
            )
        }
        SimulatedMarkers(
            equipment = equipment,
            inspection = inspection,
            onNodeSelected = onNodeSelected,
            modifier = Modifier.fillMaxSize()
        )
    }
}

@Composable
private fun SimulatedMarkers(
    equipment: Equipment,
    inspection: InspectResponse?,
    onNodeSelected: (EquipmentComponent) -> Unit,
    modifier: Modifier = Modifier
) {
    BoxWithConstraints(modifier = modifier) {
        val width = maxWidth
        val height = maxHeight

        Box(
            modifier = Modifier
                .offset(
                    x = width * 0.5f - 26.dp,
                    y = height * 0.52f
                )
                .border(1.dp, HudCyan.copy(alpha = 0.5f), CircleShape)
                .size(52.dp),
            contentAlignment = Alignment.Center
        ) {
            Box(
                Modifier
                    .size(4.dp)
                    .background(HudCyan, CircleShape)
            )
        }
        MonoLabel(
            "БАЗА QR",
            modifier = Modifier.offset(x = width * 0.5f - 24.dp, y = height * 0.52f + 56.dp),
            color = HudCyan
        )

        equipment.components.forEach { component ->
            val defect = inspection?.defects?.firstOrNull { it.nodeId == component.id }
            val critical = defect != null && (defect.isCritical || inspection.isCritical)
            val accent = when {
                critical -> HudRed
                defect != null -> SafetyYellow
                else -> HudCyan
            }
            val depth = (1f + component.offsetFromQr.z).coerceIn(0.6f, 1.8f)
            val x = width * (0.5f + component.offsetFromQr.x * 0.55f / depth)
            val y = height * (0.48f - component.offsetFromQr.y * 0.42f / depth)

            Column(
                modifier = Modifier
                    .offset(x = x - 62.dp, y = y - 16.dp)
                    .width(124.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(HudBlack.copy(alpha = 0.72f))
                    .border(1.dp, accent.copy(alpha = 0.7f), RoundedCornerShape(6.dp))
                    .clickable { onNodeSelected(component) }
                    .padding(horizontal = 6.dp, vertical = 6.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Box(
                    Modifier
                        .size(if (critical) 10.dp else 7.dp)
                        .background(accent, CircleShape)
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = component.name,
                    style = MaterialTheme.typography.labelSmall,
                    color = TextPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun ArLoading() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HudBlack),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = SafetyYellow)
            Spacer(Modifier.height(14.dp))
            MonoLabel("Проверка ARCore…", color = TextDim)
        }
    }
}
