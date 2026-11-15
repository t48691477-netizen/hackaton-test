package ru.cyber102.arinspector.util

import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import androidx.core.content.FileProvider
import ru.cyber102.arinspector.data.Defect
import ru.cyber102.arinspector.data.Equipment
import ru.cyber102.arinspector.data.EquipmentComponent
import ru.cyber102.arinspector.data.ResolutionStatus
import java.io.File
import java.io.FileOutputStream
import java.time.Instant

object PdfAct {

    private const val PAGE_WIDTH = 595
    private const val PAGE_HEIGHT = 842
    private const val MARGIN = 42f

    fun build(
        context: Context,
        equipment: Equipment,
        component: EquipmentComponent?,
        defect: Defect?,
        status: ResolutionStatus,
        comment: String,
        reportId: String
    ): File {
        val dir = File(context.cacheDir, "reports").apply { mkdirs() }
        val safeId = reportId.ifBlank { "act" }.replace(Regex("[^A-Za-z0-9_-]"), "_")
        val file = File(dir, "act-$safeId.pdf")

        val document = PdfDocument()
        val pageInfo = PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, 1).create()
        val page = document.startPage(pageInfo)
        val canvas = page.canvas

        val yellow = Color.rgb(255, 196, 0)
        val black = Color.rgb(7, 10, 12)
        val dark = Color.rgb(28, 34, 38)
        val muted = Color.rgb(96, 108, 115)

        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = dark
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL)
        }

        canvas.drawRect(0f, 0f, PAGE_WIDTH.toFloat(), 92f, Paint().apply { color = black })
        canvas.drawRect(0f, 86f, PAGE_WIDTH.toFloat(), 92f, Paint().apply { color = yellow })

        val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = yellow
            textSize = 20f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
        }
        canvas.drawText("АКТ ТЕХНИЧЕСКОГО ОСМОТРА", MARGIN, 42f, titlePaint)

        val subPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 10f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL)
        }
        canvas.drawText("AR-ИНСПЕКТОР · КИБЕР 102 · АВТОМАТИЧЕСКИЙ ОТЧЁТ", MARGIN, 60f, subPaint)
        canvas.drawText("№ $reportId", MARGIN, 76f, subPaint)

        var y = 126f
        y = section(canvas, "ОБОРУДОВАНИЕ", y, yellow)
        y = keyValue(canvas, "ID", equipment.id, y, paint, muted)
        y = keyValue(canvas, "Наименование", equipment.name, y, paint, muted)
        y = keyValue(canvas, "Расположение", equipment.location ?: "—", y, paint, muted)
        y = keyValue(canvas, "Дата осмотра", Instant.now().toString(), y, paint, muted)

        y += 8f
        y = section(canvas, "УЗЕЛ", y, yellow)
        y = keyValue(canvas, "ID", component?.id ?: "—", y, paint, muted)
        y = keyValue(canvas, "Название", component?.name ?: "—", y, paint, muted)
        if (component != null) {
            y = keyValue(
                canvas,
                "Смещение от QR",
                "x=%.2f  y=%.2f  z=%.2f м".format(
                    component.offsetFromQr.x,
                    component.offsetFromQr.y,
                    component.offsetFromQr.z
                ),
                y, paint, muted
            )
        }

        y += 8f
        y = section(canvas, "ОБНАРУЖЕННЫЙ ДЕФЕКТ", y, yellow)
        y = keyValue(canvas, "Тип", defect?.displayTitle ?: "Дефектов не обнаружено", y, paint, muted)
        if (defect != null) {
            y = keyValue(
                canvas,
                "Уверенность модели",
                "${(defect.confidence * 100).toInt()} %",
                y, paint, muted
            )
            y = keyValue(canvas, "Критичность", defect.severity.uppercase(), y, paint, muted)
        }

        if (defect?.analysis != null) {
            y += 8f
            y = section(canvas, "ИНЖЕНЕРНЫЙ АНАЛИЗ (LLM)", y, yellow)
            val body = Paint(paint).apply { textSize = 10.5f }
            y = drawWrapped(canvas, defect.analysis, body, MARGIN, y, PAGE_WIDTH - MARGIN * 2, 14.5f)
        }

        if (defect?.recommendation != null) {
            y += 8f
            y = section(canvas, "РЕКОМЕНДАЦИЯ", y, yellow)
            val body = Paint(paint).apply { textSize = 10.5f }
            y = drawWrapped(canvas, defect.recommendation, body, MARGIN, y, PAGE_WIDTH - MARGIN * 2, 14.5f)
        }

        y += 8f
        y = section(canvas, "РЕШЕНИЕ ИНЖЕНЕРА", y, yellow)
        y = keyValue(canvas, "Статус", status.label, y, paint, muted)
        if (comment.isNotBlank()) {
            val body = Paint(paint).apply { textSize = 10.5f }
            y = drawWrapped(canvas, comment, body, MARGIN, y, PAGE_WIDTH - MARGIN * 2, 14.5f)
        }

        val footerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = muted
            textSize = 9f
        }
        canvas.drawLine(
            MARGIN,
            PAGE_HEIGHT - 74f,
            PAGE_WIDTH - MARGIN,
            PAGE_HEIGHT - 74f,
            Paint().apply { color = Color.LTGRAY; strokeWidth = 0.8f }
        )
        canvas.drawText(
            "Документ сформирован приложением AR-Инспектор. Подпись инженера: ____________________",
            MARGIN,
            PAGE_HEIGHT - 52f,
            footerPaint
        )
        canvas.drawText(
            "Кибер 102 · $reportId",
            MARGIN,
            PAGE_HEIGHT - 38f,
            footerPaint
        )

        document.finishPage(page)
        FileOutputStream(file).use { document.writeTo(it) }
        document.close()
        return file
    }

    fun share(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Отправить акт"))
    }

    private fun section(canvas: Canvas, text: String, y: Float, accent: Int): Float {
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = accent
            textSize = 10f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
        }
        canvas.drawText(text, MARGIN, y, paint)
        canvas.drawLine(
            MARGIN,
            y + 4f,
            PAGE_WIDTH - MARGIN,
            y + 4f,
            Paint().apply { color = Color.LTGRAY; strokeWidth = 0.6f }
        )
        return y + 20f
    }

    private fun keyValue(
        canvas: Canvas,
        key: String,
        value: String,
        y: Float,
        paint: Paint,
        muted: Int
    ): Float {
        val keyPaint = Paint(paint).apply {
            color = muted
            textSize = 9f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL)
        }
        val valuePaint = Paint(paint).apply {
            color = Color.rgb(28, 34, 38)
            textSize = 10.5f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
        }
        canvas.drawText(key.uppercase(), MARGIN, y, keyPaint)
        canvas.drawText(value, MARGIN + 150f, y, valuePaint)
        return y + 16f
    }

    private fun drawWrapped(
        canvas: Canvas,
        text: String,
        paint: Paint,
        x: Float,
        startY: Float,
        maxWidth: Float,
        lineHeight: Float
    ): Float {
        var y = startY
        text.split('\n').forEach { paragraph ->
            if (paragraph.isBlank()) {
                y += lineHeight
                return@forEach
            }
            val words = paragraph.split(' ')
            var line = StringBuilder()
            words.forEach { word ->
                val candidate = if (line.isEmpty()) word else "$line $word"
                if (paint.measureText(candidate) > maxWidth && line.isNotEmpty()) {
                    canvas.drawText(line.toString(), x, y, paint)
                    y += lineHeight
                    line = StringBuilder(word)
                } else {
                    line = StringBuilder(candidate)
                }
            }
            if (line.isNotEmpty()) {
                canvas.drawText(line.toString(), x, y, paint)
                y += lineHeight
            }
        }
        return y
    }
}
