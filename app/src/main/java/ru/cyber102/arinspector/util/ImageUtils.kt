package ru.cyber102.arinspector.util

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import android.media.Image
import java.io.ByteArrayOutputStream
import kotlin.math.roundToInt

/**
 * Подготовка кадра камеры к отправке на /api/inspect.
 *
 * Важно: кадр поворачивается в портрет и центрально обрезается под аспект экрана.
 * Тогда нормализованные координаты полигонов из ответа (0..1) один-в-один
 * ложатся на Canvas-оверлей экрана.
 */
object ImageUtils {

    private const val MAX_UPLOAD_WIDTH = 960
    private const val JPEG_QUALITY = 82

    data class YuvFrame(
        val width: Int,
        val height: Int,
        val nv21: ByteArray
    )

    /** Быстро копирует YUV_420_888 из ARCore в NV21. Вызывать в onSessionUpdated. */
    fun toYuvFrame(image: Image): YuvFrame {
        val width = image.width
        val height = image.height
        val ySize = width * height
        val nv21 = ByteArray(ySize + ySize / 2)

        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]

        copyPlane(yPlane, nv21, 0, width, height)

        val chromaHeight = height / 2
        val chromaWidth = width / 2
        var offset = ySize
        val uBuffer = uPlane.buffer
        val vBuffer = vPlane.buffer
        for (row in 0 until chromaHeight) {
            for (col in 0 until chromaWidth) {
                nv21[offset++] = vBuffer.get(row * vPlane.rowStride + col * vPlane.pixelStride)
                nv21[offset++] = uBuffer.get(row * uPlane.rowStride + col * uPlane.pixelStride)
            }
        }
        return YuvFrame(width, height, nv21)
    }

    private fun copyPlane(plane: Image.Plane, out: ByteArray, offset: Int, width: Int, height: Int) {
        val buffer = plane.buffer
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        if (pixelStride == 1 && rowStride == width) {
            buffer.get(out, offset, width * height)
            return
        }
        var position = offset
        for (row in 0 until height) {
            var index = row * rowStride
            for (col in 0 until width) {
                out[position++] = buffer.get(index)
                index += pixelStride
            }
        }
    }

    fun yuvToUploadJpeg(frame: YuvFrame, rotationDegrees: Int, targetAspect: Float): ByteArray? {
        val yuv = YuvImage(frame.nv21, ImageFormat.NV21, frame.width, frame.height, null)
        val out = ByteArrayOutputStream()
        if (!yuv.compressToJpeg(Rect(0, 0, frame.width, frame.height), 92, out)) return null
        val bytes = out.toByteArray()
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return null
        return bitmapToUploadJpeg(bitmap, rotationDegrees, targetAspect)
    }

    fun jpegToUploadJpeg(jpeg: ByteArray, rotationDegrees: Int, targetAspect: Float): ByteArray? {
        val bitmap = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size) ?: return null
        return bitmapToUploadJpeg(bitmap, rotationDegrees, targetAspect)
    }

    fun bitmapToUploadJpeg(src: Bitmap, rotationDegrees: Int, targetAspect: Float): ByteArray {
        val upright = if (rotationDegrees % 360 == 0) {
            src
        } else {
            Bitmap.createBitmap(
                src,
                0,
                0,
                src.width,
                src.height,
                Matrix().apply { postRotate(rotationDegrees.toFloat()) },
                true
            )
        }
        val cropped = centerCrop(upright, targetAspect)
        val scaled = if (cropped.width > MAX_UPLOAD_WIDTH) {
            val height = (cropped.height * (MAX_UPLOAD_WIDTH.toFloat() / cropped.width)).roundToInt()
            Bitmap.createScaledBitmap(cropped, MAX_UPLOAD_WIDTH, height, true)
        } else {
            cropped
        }
        val out = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
        return out.toByteArray()
    }

    private fun centerCrop(bitmap: Bitmap, targetAspect: Float): Bitmap {
        if (targetAspect <= 0f) return bitmap
        val width = bitmap.width
        val height = bitmap.height
        val currentAspect = width.toFloat() / height
        return if (currentAspect > targetAspect) {
            val croppedWidth = (height * targetAspect).roundToInt().coerceAtLeast(1)
            Bitmap.createBitmap(bitmap, (width - croppedWidth) / 2, 0, croppedWidth, height)
        } else {
            val croppedHeight = (width / targetAspect).roundToInt().coerceAtLeast(1)
            Bitmap.createBitmap(bitmap, 0, (height - croppedHeight) / 2, width, croppedHeight)
        }
    }
}
