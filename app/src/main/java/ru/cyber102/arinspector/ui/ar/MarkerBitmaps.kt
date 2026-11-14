package ru.cyber102.arinspector.ui.ar

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface

/**
 * Плашки с названиями узлов для 3D-сцены: генерируем Bitmap и вешаем его на ImageNode.
 */
object MarkerBitmaps {

    fun label(text: String, accent: Int, critical: Boolean): Bitmap {
        val width = 512
        val height = 128
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        val rect = RectF(2f, 2f, width - 2f, height - 2f)
        canvas.drawRoundRect(rect, 18f, 18f, Paint().apply { color = 0xE60B0F12.toInt() })
        canvas.drawRoundRect(
            rect,
            18f,
            18f,
            Paint().apply {
                style = Paint.Style.STROKE
                strokeWidth = 4f
                color = accent
            }
        )
        canvas.drawRoundRect(
            RectF(10f, 20f, 24f, height - 20f),
            7f,
            7f,
            Paint().apply { color = accent }
        )

        val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 46f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
        }
        val maxWidth = width - 120f
        while (textPaint.measureText(text) > maxWidth && textPaint.textSize > 24f) {
            textPaint.textSize -= 2f
        }
        val metrics = textPaint.fontMetrics
        val baseline = height / 2f - (metrics.ascent + metrics.descent) / 2f
        canvas.drawText(text, 38f, baseline, textPaint)

        canvas.drawCircle(
            width - 36f,
            height / 2f,
            11f,
            Paint(Paint.ANTI_ALIAS_FLAG).apply { color = accent }
        )
        if (critical) {
            val markPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = accent
                textSize = 34f
                typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
            }
            canvas.drawText("!", width - 44f, height / 2f + 12f, markPaint)
        }

        return bitmap
    }
}
