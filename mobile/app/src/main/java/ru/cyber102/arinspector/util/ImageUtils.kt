package ru.cyber102.arinspector.util

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.ImageProxy
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.roundToInt

data class CapturedFrame(
    val jpegBytes: ByteArray,
    val width: Int,
    val height: Int
)

object ImageUtils {
    private const val MAX_LONG_SIDE_PX = 640
    private const val JPEG_QUALITY = 70

    fun imageProxyToCapturedFrame(imageProxy: ImageProxy): CapturedFrame {
        val rotationDegrees = imageProxy.imageInfo.rotationDegrees
        val baseBitmap = imageProxy.toBitmap()

        val rotatedBitmap = if (rotationDegrees != 0) {
            val matrix = Matrix().apply { postRotate(rotationDegrees.toFloat()) }
            Bitmap.createBitmap(
                baseBitmap,
                0,
                0,
                baseBitmap.width,
                baseBitmap.height,
                matrix,
                true
            ).also {
                if (it != baseBitmap) baseBitmap.recycle()
            }
        } else {
            baseBitmap
        }

        val longSide = max(rotatedBitmap.width, rotatedBitmap.height)
        val finalBitmap = if (longSide > MAX_LONG_SIDE_PX) {
            val scale = MAX_LONG_SIDE_PX.toFloat() / longSide.toFloat()
            val targetW = (rotatedBitmap.width * scale).roundToInt().coerceAtLeast(1)
            val targetH = (rotatedBitmap.height * scale).roundToInt().coerceAtLeast(1)
            Bitmap.createScaledBitmap(rotatedBitmap, targetW, targetH, true).also {
                if (it != rotatedBitmap) rotatedBitmap.recycle()
            }
        } else {
            rotatedBitmap
        }

        val stream = ByteArrayOutputStream()
        finalBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, stream)
        val resultWidth = finalBitmap.width
        val resultHeight = finalBitmap.height
        finalBitmap.recycle()

        return CapturedFrame(
            jpegBytes = stream.toByteArray(),
            width = resultWidth,
            height = resultHeight
        )
    }
}
