package ru.cyber102.arinspector.ui.scanner

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.annotation.OptIn
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import com.google.accompanist.permissions.shouldShowRationale
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.EquipmentStateBadge
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.ProbabilityBarRow
import ru.cyber102.arinspector.ui.components.SecondaryActionButton
import ru.cyber102.arinspector.ui.components.SeverityBadge
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.ImageUtils
import ru.cyber102.arinspector.util.PdfGenerator
import ru.cyber102.arinspector.util.QrParser
import java.util.concurrent.Executors

@kotlin.OptIn(ExperimentalPermissionsApi::class)
@Composable
fun ScannerScreen(
    viewModel: ScannerViewModel,
    onOpenSettings: () -> Unit,
    onNavigateToTasks: () -> Unit,
    onShowMessage: (String) -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val cameraPermissionState = rememberPermissionState(Manifest.permission.CAMERA)
    var hasRequestedPermission by rememberSaveable { mutableStateOf(false) }

    val noFrameMsg = stringResource(R.string.scanner_no_frame_yet)
    val reportCreatedMsg = stringResource(R.string.scanner_create_report_success)
    val pdfErrorMsg = stringResource(R.string.scanner_pdf_error)
    val sharePdfTitle = stringResource(R.string.scanner_share_pdf_title)

    LaunchedEffect(uiState.snackbarMessage) {
        val msg = uiState.snackbarMessage
        if (!msg.isNullOrBlank()) {
            onShowMessage(msg)
            viewModel.consumeSnackbar()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        if (cameraPermissionState.status.isGranted) {
            CameraPreviewAndAnalyzer(
                viewModel = viewModel,
                isAnalyzing = uiState.isAnalyzing,
                hasEquipment = uiState.equipment != null
            )

            DefectOverlayCanvas(
                defects = uiState.latestInspection?.defects.orEmpty(),
                frameWidth = uiState.frameWidth,
                frameHeight = uiState.frameHeight
            )

            // Верхняя инженерная панель поверх камеры
            ScannerTopOverlay(
                equipmentName = uiState.equipment?.name ?: uiState.equipment?.id,
                equipmentState = uiState.equipment?.state,
                isAnalyzing = uiState.isAnalyzing,
                onOpenPassport = { viewModel.openPassportSheet(true) },
                onClearEquipment = viewModel::clearEquipment,
                onManualIdClick = { viewModel.setShowManualIdDialog(true) },
                onOpenSettings = onOpenSettings,
                modifier = Modifier.align(Alignment.TopCenter)
            )

            if (uiState.isEquipmentLoading) {
                Surface(
                    shape = PromScanShapesTokens.Card,
                    color = KstColors.Surface.copy(alpha = 0.94f),
                    border = BorderStroke(1.dp, KstColors.Border),
                    modifier = Modifier.align(Alignment.Center)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 20.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = KstColors.Accent,
                            strokeWidth = 2.5.dp
                        )
                        Text(
                            text = stringResource(R.string.scanner_loading_equipment),
                            style = MaterialTheme.typography.bodyMedium,
                            color = KstColors.TextPrimary
                        )
                    }
                }
            }

            // Нижняя панель управления
            if (uiState.equipment == null) {
                QrIdleBottomBar(
                    onManualIdClick = { viewModel.setShowManualIdDialog(true) },
                    modifier = Modifier.align(Alignment.BottomCenter)
                )
            } else {
                InspectionSummaryBottomPanel(
                    uiState = uiState,
                    onToggleAnalysis = viewModel::toggleAnalysis,
                    onDetailedClick = { viewModel.requestDetailedAnalysis(noFrameMsg) },
                    onCreateReportClick = { viewModel.setShowCreateReportDialog(true, noFrameMsg) },
                    onExportPdfClick = {
                        val eq = uiState.equipment
                        val insp = uiState.latestInspection
                        if (eq == null || insp == null) {
                            viewModel.showMessage(noFrameMsg)
                        } else {
                            scope.launch {
                                val uri = withContext(Dispatchers.IO) {
                                    runCatching {
                                        PdfGenerator.createInspectionActPdf(
                                            context = context,
                                            equipment = eq,
                                            inspection = insp,
                                            frameJpeg = uiState.lastFrameJpeg
                                        )
                                    }.getOrNull()
                                }
                                if (uri != null) {
                                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = "application/pdf"
                                        putExtra(Intent.EXTRA_STREAM, uri)
                                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                    }
                                    context.startActivity(
                                        Intent.createChooser(shareIntent, sharePdfTitle)
                                    )
                                } else {
                                    viewModel.showMessage(pdfErrorMsg)
                                }
                            }
                        }
                    },
                    modifier = Modifier.align(Alignment.BottomCenter)
                )
            }
        } else {
            CameraPermissionPlaceholder(
                shouldShowRationale = !hasRequestedPermission || cameraPermissionState.status.shouldShowRationale,
                onRequestPermission = {
                    hasRequestedPermission = true
                    cameraPermissionState.launchPermissionRequest()
                },
                onOpenAppSettings = {
                    val intent = Intent(
                        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.fromParts("package", context.packageName, null)
                    )
                    context.startActivity(intent)
                },
                onManualIdClick = { viewModel.setShowManualIdDialog(true) },
                onOpenSettings = onOpenSettings
            )
        }
    }

    if (uiState.showPassportSheet && uiState.equipment != null) {
        EquipmentPassportSheet(
            equipment = uiState.equipment!!,
            onDismiss = { viewModel.openPassportSheet(false) },
            onStartAnalysis = {
                if (!uiState.isAnalyzing) viewModel.toggleAnalysis()
                viewModel.openPassportSheet(false)
            },
            onChangeEquipment = { viewModel.clearEquipment() }
        )
    }

    if (uiState.showDetailedSheet && uiState.detailedResult != null) {
        DetailedInspectionSheet(
            detail = uiState.detailedResult!!,
            onDismiss = viewModel::dismissDetailedSheet
        )
    }

    if (uiState.showManualIdDialog) {
        ManualEquipmentIdDialog(
            options = uiState.equipmentOptions,
            onDismiss = { viewModel.setShowManualIdDialog(false) },
            onConfirm = { id -> viewModel.loadEquipment(id) }
        )
    }

    if (uiState.showCreateReportDialog) {
        CreateReportDialog(
            isSubmitting = uiState.isCreatingReport,
            onDismiss = { viewModel.setShowCreateReportDialog(false) },
            onSubmit = { comment ->
                viewModel.createReport(
                    comment = comment,
                    successMessage = reportCreatedMsg,
                    onCreated = onNavigateToTasks
                )
            }
        )
    }
}

@OptIn(ExperimentalGetImage::class)
@Composable
private fun CameraPreviewAndAnalyzer(
    viewModel: ScannerViewModel,
    isAnalyzing: Boolean,
    hasEquipment: Boolean
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val currentIsAnalyzing by rememberUpdatedState(isAnalyzing)
    val currentHasEquipment by rememberUpdatedState(hasEquipment)

    val analyzerExecutor = remember { Executors.newSingleThreadExecutor() }
    val barcodeScanner = remember {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                .build()
        )
    }

    DisposableEffect(Unit) {
        onDispose {
            barcodeScanner.close()
            analyzerExecutor.shutdown()
        }
    }

    AndroidView(
        factory = { ctx ->
            val previewView = PreviewView(ctx).apply {
                scaleType = PreviewView.ScaleType.FILL_CENTER
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            }
            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()
                val resolutionSelector = ResolutionSelector.Builder()
                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
                    .build()

                val preview = Preview.Builder()
                    .setResolutionSelector(resolutionSelector)
                    .build()
                    .apply {
                        surfaceProvider = previewView.surfaceProvider
                    }

                val imageAnalysis = ImageAnalysis.Builder()
                    .setResolutionSelector(resolutionSelector)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()

                imageAnalysis.setAnalyzer(analyzerExecutor) { imageProxy ->
                    val rotation = imageProxy.imageInfo.rotationDegrees
                    val uprightW = if (rotation == 90 || rotation == 270) imageProxy.height else imageProxy.width
                    val uprightH = if (rotation == 90 || rotation == 270) imageProxy.width else imageProxy.height
                    viewModel.updateFrameDimensions(uprightW, uprightH)

                    if (!currentHasEquipment && !currentIsAnalyzing) {
                        val mediaImage = imageProxy.image
                        if (mediaImage != null) {
                            val inputImage = InputImage.fromMediaImage(mediaImage, rotation)
                            barcodeScanner.process(inputImage)
                                .addOnSuccessListener { barcodes ->
                                    val firstRaw = barcodes.firstOrNull { !it.rawValue.isNullOrBlank() }?.rawValue
                                    val eqId = QrParser.extractEquipmentId(firstRaw)
                                    if (!eqId.isNullOrBlank()) {
                                        viewModel.onQrDetected(eqId)
                                    }
                                }
                                .addOnCompleteListener {
                                    imageProxy.close()
                                }
                        } else {
                            imageProxy.close()
                        }
                    } else if (currentIsAnalyzing && viewModel.tryAcquireFrameCaptureSlot()) {
                        try {
                            val captured = ImageUtils.imageProxyToCapturedFrame(imageProxy)
                            imageProxy.close()
                            viewModel.submitCapturedFrame(captured)
                        } catch (_: Exception) {
                            imageProxy.close()
                            viewModel.releaseFrameCaptureSlotOnError()
                        }
                    } else {
                        imageProxy.close()
                    }
                }

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageAnalysis
                    )
                } catch (_: Exception) {
                    // Обработка отсутствия камеры на эмуляторах без аппаратной камеры.
                }
            }, ContextCompat.getMainExecutor(ctx))

            previewView
        },
        modifier = Modifier.fillMaxSize()
    )
}

@Composable
private fun ScannerTopOverlay(
    equipmentName: String?,
    equipmentState: String?,
    isAnalyzing: Boolean,
    onOpenPassport: () -> Unit,
    onClearEquipment: () -> Unit,
    onManualIdClick: () -> Unit,
    onOpenSettings: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        color = KstColors.NavyDark.copy(alpha = 0.92f),
        contentColor = KstColors.White,
        modifier = modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .then(
                        if (equipmentName != null) {
                            Modifier.clickable(onClick = onOpenPassport)
                        } else {
                            Modifier
                        }
                    )
                    .padding(horizontal = 4.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = stringResource(R.string.brand_header_title),
                        style = MaterialTheme.typography.titleMedium,
                        color = KstColors.White,
                        fontWeight = FontWeight.SemiBold
                    )
                    if (isAnalyzing) {
                        Surface(
                            color = KstColors.Error,
                            shape = CircleShape
                        ) {
                            Text(
                                text = stringResource(R.string.scanner_analyzing_badge),
                                style = MaterialTheme.typography.labelSmall,
                                color = KstColors.White,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                            )
                        }
                    }
                }
                if (equipmentName != null) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Text(
                            text = equipmentName,
                            style = MaterialTheme.typography.bodySmall,
                            color = KstColors.White.copy(alpha = 0.9f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f, fill = false)
                        )
                        if (equipmentState != null) {
                            EquipmentStateBadge(state = equipmentState)
                        }
                    }
                }
            }

            if (equipmentName != null) {
                IconButton(
                    onClick = onOpenPassport,
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("open_passport_button")
                ) {
                    Icon(
                        imageVector = Icons.Filled.Info,
                        contentDescription = stringResource(R.string.scanner_passport_title),
                        tint = KstColors.White
                    )
                }
                IconButton(
                    onClick = onClearEquipment,
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("clear_equipment_button")
                ) {
                    Icon(
                        imageVector = Icons.Filled.Close,
                        contentDescription = stringResource(R.string.scanner_change_equipment),
                        tint = KstColors.White
                    )
                }
            } else {
                IconButton(
                    onClick = onManualIdClick,
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("top_manual_id_button")
                ) {
                    Icon(
                        imageVector = Icons.Filled.Edit,
                        contentDescription = stringResource(R.string.scanner_manual_id_button),
                        tint = KstColors.White
                    )
                }
            }

            IconButton(
                onClick = onOpenSettings,
                modifier = Modifier
                    .size(48.dp)
                    .testTag("scanner_settings_button")
            ) {
                Icon(
                    imageVector = Icons.Filled.Settings,
                    contentDescription = stringResource(R.string.cd_settings),
                    tint = KstColors.White
                )
            }
        }
    }
}

@Composable
private fun QrIdleBottomBar(
    onManualIdClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    EngineeringCard(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_qr_scanner),
                    contentDescription = null,
                    tint = KstColors.Accent,
                    modifier = Modifier.size(28.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = stringResource(R.string.scanner_qr_prompt),
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextPrimary
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
            SecondaryActionButton(
                text = stringResource(R.string.scanner_manual_id_button),
                onClick = onManualIdClick,
                modifier = Modifier.testTag("bottom_manual_id_button")
            )
        }
    }
}

@Composable
private fun InspectionSummaryBottomPanel(
    uiState: ScannerUiState,
    onToggleAnalysis: () -> Unit,
    onDetailedClick: () -> Unit,
    onCreateReportClick: () -> Unit,
    onExportPdfClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val inspection = uiState.latestInspection
    EngineeringCard(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 12.dp),
        contentPadding = PaddingValues(14.dp)
    ) {
        if (inspection != null) {
            val maxDefectSeverity = inspection.defects?.maxOfOrNull {
                when (it.resolvedSeverity) {
                    "high" -> 2
                    "medium" -> 1
                    else -> 0
                }
            } ?: 0
            val llmRank = when (inspection.llm?.criticality?.lowercase()) {
                "high" -> 2
                "medium" -> 1
                else -> 0
            }
            val criticality = when (maxOf(llmRank, maxDefectSeverity)) {
                2 -> "high"
                1 -> "medium"
                else -> "low"
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                SeverityBadge(severity = criticality)
                if (uiState.isInspectInFlight) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        color = KstColors.Accent,
                        strokeWidth = 2.dp
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            val params = inspection.conditionParameters
            ProbabilityBarRow(
                label = stringResource(R.string.param_oil_leak),
                probability = params?.oilLeakProbability
            )
            Spacer(modifier = Modifier.height(6.dp))
            ProbabilityBarRow(
                label = stringResource(R.string.param_rust),
                probability = params?.rustProbability
            )
            Spacer(modifier = Modifier.height(6.dp))
            ProbabilityBarRow(
                label = stringResource(R.string.param_poor_weld),
                probability = params?.poorWeldProbability
            )

            val summaryText = inspection.summary
            if (!summaryText.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = summaryText,
                    style = MaterialTheme.typography.bodySmall,
                    color = KstColors.TextPrimary,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Spacer(modifier = Modifier.height(12.dp))
        }

        // Главная кнопка Анализ / Стоп
        Button(
            onClick = onToggleAnalysis,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .testTag("toggle_analysis_button"),
            shape = PromScanShapesTokens.Control,
            colors = ButtonDefaults.buttonColors(
                containerColor = if (uiState.isAnalyzing) KstColors.Error else KstColors.Accent,
                contentColor = KstColors.White
            )
        ) {
            if (uiState.isAnalyzing) {
                Icon(
                    painter = painterResource(R.drawable.ic_stop),
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.scanner_analyze_stop),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            } else {
                Icon(
                    imageVector = Icons.Filled.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.scanner_analyze_start),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }

        if (inspection != null) {
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onDetailedClick,
                    enabled = !uiState.isDetailedLoading,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 48.dp)
                        .testTag("detailed_conclusion_button"),
                    shape = PromScanShapesTokens.Control,
                    border = BorderStroke(1.dp, KstColors.Border),
                    contentPadding = PaddingValues(horizontal = 6.dp)
                ) {
                    if (uiState.isDetailedLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = KstColors.Accent,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = stringResource(R.string.scanner_conclusion_button),
                            style = MaterialTheme.typography.labelMedium,
                            color = KstColors.TextPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                OutlinedButton(
                    onClick = onCreateReportClick,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 48.dp)
                        .testTag("create_report_button"),
                    shape = PromScanShapesTokens.Control,
                    border = BorderStroke(1.dp, KstColors.Accent),
                    contentPadding = PaddingValues(horizontal = 6.dp)
                ) {
                    Text(
                        text = stringResource(R.string.scanner_create_report_button),
                        style = MaterialTheme.typography.labelMedium,
                        color = KstColors.Accent,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                OutlinedButton(
                    onClick = onExportPdfClick,
                    modifier = Modifier
                        .weight(0.85f)
                        .heightIn(min = 48.dp)
                        .testTag("export_pdf_button"),
                    shape = PromScanShapesTokens.Control,
                    border = BorderStroke(1.dp, KstColors.Border),
                    contentPadding = PaddingValues(horizontal = 6.dp)
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_pdf),
                        contentDescription = null,
                        tint = KstColors.TextPrimary,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = stringResource(R.string.scanner_pdf_button),
                        style = MaterialTheme.typography.labelMedium,
                        color = KstColors.TextPrimary,
                        maxLines = 1
                    )
                }
            }
        }
    }
}

@Composable
private fun CameraPermissionPlaceholder(
    shouldShowRationale: Boolean,
    onRequestPermission: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onManualIdClick: () -> Unit,
    onOpenSettings: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        Surface(
            color = KstColors.NavyDark,
            contentColor = KstColors.White
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = stringResource(R.string.brand_header_title),
                    style = MaterialTheme.typography.titleLarge,
                    color = KstColors.White
                )
                IconButton(
                    onClick = onOpenSettings,
                    modifier = Modifier.size(48.dp)
                ) {
                    Icon(
                        imageVector = Icons.Filled.Settings,
                        contentDescription = stringResource(R.string.cd_settings),
                        tint = KstColors.White
                    )
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            EngineeringCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 460.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(KstColors.AccentTint),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_qr_scanner),
                        contentDescription = null,
                        tint = KstColors.Accent,
                        modifier = Modifier.size(28.dp)
                    )
                }
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(
                        if (shouldShowRationale) {
                            R.string.scanner_permission_title
                        } else {
                            R.string.scanner_permission_denied_title
                        }
                    ),
                    style = MaterialTheme.typography.titleLarge,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = stringResource(
                        if (shouldShowRationale) {
                            R.string.scanner_permission_rationale
                        } else {
                            R.string.scanner_permission_denied_desc
                        }
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextSecondary,
                    textAlign = TextAlign.Start
                )
                Spacer(modifier = Modifier.height(20.dp))
                PrimaryActionButton(
                    text = stringResource(
                        if (shouldShowRationale) {
                            R.string.scanner_permission_grant
                        } else {
                            R.string.scanner_open_app_settings
                        }
                    ),
                    onClick = {
                        if (shouldShowRationale) onRequestPermission() else onOpenAppSettings()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("camera_permission_action_button")
                )
                Spacer(modifier = Modifier.height(10.dp))
                SecondaryActionButton(
                    text = stringResource(R.string.scanner_manual_id_button),
                    onClick = onManualIdClick,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}
