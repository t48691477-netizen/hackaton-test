package ru.cyber102.arinspector.ui.scanner

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.cyber102.arinspector.data.model.DefectDto
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.util.Formatters
import kotlin.math.max
import kotlin.math.roundToInt

@Composable
fun DefectOverlayCanvas(
    defects: List<DefectDto>,
    frameWidth: Int,
    frameHeight: Int,
    modifier: Modifier = Modifier
) {
    val textMeasurer = rememberTextMeasurer()

    Canvas(modifier = modifier.fillMaxSize()) {
        if (frameWidth <= 0 || frameHeight <= 0 || defects.isEmpty()) return@Canvas

        val viewW = size.width
        val viewH = size.height
        val scale = max(viewW / frameWidth.toFloat(), viewH / frameHeight.toFloat())
        val scaledW = frameWidth * scale
        val scaledH = frameHeight * scale
        val offsetX = (viewW - scaledW) / 2f
        val offsetY = (viewH - scaledH) / 2f

        fun toScreen(nx: Double, ny: Double): Offset {
            val sx = (nx.toFloat().coerceIn(0f, 1f) * scaledW) + offsetX
            val sy = (ny.toFloat().coerceIn(0f, 1f) * scaledH) + offsetY
            return Offset(sx, sy)
        }

        val strokeWidthPx = 2.5.dp.toPx()
        val cornerRadiusPx = 6.dp.toPx()
        val labelPadH = 8.dp.toPx()
        val labelPadV = 4.dp.toPx()

        defects.forEach { defect ->
            val color = when (defect.severity?.lowercase()) {
                "high" -> KstColors.Error
                "medium" -> KstColors.SeverityMedium
                else -> KstColors.SeverityLow
            }

            var anchorX = 0f
            var anchorY = 0f
            var hasGeometry = false

            val polygon = defect.polygon
            if (!polygon.isNullOrEmpty() && polygon.size >= 3) {
                val path = Path()
                var minY = Float.MAX_VALUE
                var minXAtMinY = Float.MAX_VALUE
                polygon.forEachIndexed { idx, pt ->
                    if (pt.size >= 2) {
                        val p = toScreen(pt[0], pt[1])
                        if (!hasGeometry) {
                            path.moveTo(p.x, p.y)
                            hasGeometry = true
                        } else {
                            path.lineTo(p.x, p.y)
                        }
                        if (p.y < minY) {
                            minY = p.y
                            minXAtMinY = p.x
                        }
                    }
                }
                if (hasGeometry) {
                    path.close()
                    drawPath(path = path, color = color.copy(alpha = 0.22f))
                    drawPath(path = path, color = color, style = Stroke(width = strokeWidthPx))
                    anchorX = minXAtMinY
                    anchorY = minY
                }
            }

            if (!hasGeometry) {
                val bbox = defect.bbox
                if (bbox != null && bbox.size >= 4) {
                    val topLeft = toScreen(bbox[0], bbox[1])
                    val bottomRight = toScreen(bbox[2], bbox[3])
                    val rectW = (bottomRight.x - topLeft.x).coerceAtLeast(2f)
                    val rectH = (bottomRight.y - topLeft.y).coerceAtLeast(2f)
                    drawRect(
                        color = color.copy(alpha = 0.14f),
                        topLeft = topLeft,
                        size = Size(rectW, rectH)
                    )
                    drawRect(
                        color = color,
                        topLeft = topLeft,
                        size = Size(rectW, rectH),
                        style = Stroke(width = strokeWidthPx)
                    )
                    anchorX = topLeft.x
                    anchorY = topLeft.y
                    hasGeometry = true
                }
            }

            if (hasGeometry) {
                val pct = ((defect.confidence ?: 0.0) * 100.0).roundToInt()
                val sevWord = Formatters.severityLabel(defect.severity)
                val title = "${defect.label ?: "Дефект"} $pct% · $sevWord"

                val measured = textMeasurer.measure(
                    text = title,
                    style = TextStyle(
                        color = Color.White,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                )
                val pillW = measured.size.width + labelPadH * 2f
                val pillH = measured.size.height + labelPadV * 2f

                val clampedX = anchorX.coerceIn(4f, (viewW - pillW - 4f).coerceAtLeast(4f))
                val preferredY = if (anchorY - pillH - 4f >= 4f) anchorY - pillH - 4f else anchorY + 4f
                val clampedY = preferredY.coerceIn(4f, (viewH - pillH - 4f).coerceAtLeast(4f))

                drawRoundRect(
                    color = Color.Black.copy(alpha = 0.78f),
                    topLeft = Offset(clampedX, clampedY),
                    size = Size(pillW, pillH),
                    cornerRadius = CornerRadius(cornerRadiusPx, cornerRadiusPx)
                )
                drawRoundRect(
                    color = color,
                    topLeft = Offset(clampedX, clampedY),
                    size = Size(pillW, pillH),
                    cornerRadius = CornerRadius(cornerRadiusPx, cornerRadiusPx),
                    style = Stroke(width = 1.5.dp.toPx())
                )
                drawText(
                    textLayoutResult = measured,
                    topLeft = Offset(clampedX + labelPadH, clampedY + labelPadV)
                )
            }
        }
    }
}
