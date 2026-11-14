package ru.cyber102.arinspector.ui.ar

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.NormalizedPoint
import ru.cyber102.arinspector.ui.theme.HudRed
import ru.cyber102.arinspector.ui.theme.Rust

/**
 * Canvas-оверлей поверх камеры: заливает полигоны ржавчины и рисует рамки трещин.
 * Координаты сервера нормализованы под экран (0..1), поэтому просто умножаем на размер Canvas.
 */
@Composable
fun DefectOverlay(
    defects: List<Defect>,
    modifier: Modifier = Modifier,
    onDefectTap: (Defect) -> Unit = {}
) {
    if (defects.isEmpty()) return

    val textMeasurer = rememberTextMeasurer()
    val labelStyle = TextStyle(
        color = Color.White,
        fontSize = 10.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold
    )
    val labels = remember(defects) {
        defects.associate { defect ->
            defect.id to textMeasurer.measure(
                AnnotatedString(
                    "${defect.displayTitle.uppercase()}  ${(defect.confidence * 100).toInt()}%"
                ),
                style = labelStyle
            )
        }
    }

    Canvas(
        // Тап перехватываем только внутри полигона дефекта. Иначе событие уходит
        // в AR-сцену, и 3D-маркеры остаются кликабельными даже поверх оверлея.
        modifier = modifier.pointerInput(defects) {
            awaitEachGesture {
                val down = awaitFirstDown(requireUnconsumed = false)
                val width = size.width.toFloat().coerceAtLeast(1f)
                val height = size.height.toFloat().coerceAtLeast(1f)
                val hit = defects.lastOrNull { defect ->
                    polygonContains(
                        defect.polygon,
                        down.position.x / width,
                        down.position.y / height
                    )
                }
                if (hit == null) return@awaitEachGesture

                down.consume()
                val up = waitForUpOrCancellation()
                if (up != null) {
                    up.consume()
                    onDefectTap(hit)
                }
            }
        }
    ) {
        defects.forEach { defect ->
            val color = if (defect.type.equals("crack", true)) HudRed else Rust
            val points = defect.polygon
            if (points.size >= 3) {
                val path = Path()
                points.forEachIndexed { index, point ->
                    val x = point.x * size.width
                    val y = point.y * size.height
                    if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                path.close()

                drawPath(path, color.copy(alpha = 0.26f))
                drawPath(path, color.copy(alpha = 0.95f), style = Stroke(width = 2.dp.toPx()))

                // Диагональная штриховка внутри дефекта
                clipPath(path) {
                    val step = 16.dp.toPx()
                    var x = -size.height
                    while (x < size.width + size.height) {
                        drawLine(
                            color = color.copy(alpha = 0.20f),
                            start = Offset(x, 0f),
                            end = Offset(x + size.height, size.height),
                            strokeWidth = 1.dp.toPx()
                        )
                        x += step
                    }
                }
            }

            val rect = defect.rect()
            if (rect != null && defect.type.equals("crack", true)) {
                val left = rect[0] * size.width
                val top = rect[1] * size.height
                val right = rect[2] * size.width
                val bottom = rect[3] * size.height
                drawRect(
                    color = color.copy(alpha = 0.9f),
                    topLeft = Offset(left, top),
                    size = Size((right - left).coerceAtLeast(1f), (bottom - top).coerceAtLeast(1f)),
                    style = Stroke(
                        width = 1.5.dp.toPx(),
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 8f))
                    )
                )
            }

            val layout = labels[defect.id]
            val anchor = rect ?: return@forEach
            if (layout != null) {
                val padding = 5.dp.toPx()
                val labelWidth = layout.size.width + padding * 2
                val labelHeight = layout.size.height + padding * 2
                val x = (anchor[0] * size.width).coerceIn(0f, (size.width - labelWidth).coerceAtLeast(0f))
                val y = (anchor[1] * size.height - labelHeight - 6.dp.toPx()).coerceAtLeast(0f)
                drawRoundRect(
                    color = Color(0xCC070A0C),
                    topLeft = Offset(x, y),
                    size = Size(labelWidth, labelHeight),
                    cornerRadius = CornerRadius(4.dp.toPx())
                )
                drawRect(
                    color = color,
                    topLeft = Offset(x, y),
                    size = Size(3.dp.toPx(), labelHeight)
                )
                drawText(
                    textLayoutResult = layout,
                    topLeft = Offset(x + padding + 4.dp.toPx(), y + padding)
                )
            }
        }
    }
}

private fun polygonContains(points: List<NormalizedPoint>, x: Float, y: Float): Boolean {
    if (points.size < 3) return false
    var inside = false
    var j = points.size - 1
    for (i in points.indices) {
        val xi = points[i].x
        val yi = points[i].y
        val xj = points[j].x
        val yj = points[j].y
        val intersects = (yi > y) != (yj > y) &&
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-9f) + xi
        if (intersects) inside = !inside
        j = i
    }
    return inside
}
