package ru.cyber102.arinspector.util

import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.net.Uri
import androidx.core.content.FileProvider
import ru.cyber102.arinspector.data.model.EquipmentDto
import ru.cyber102.arinspector.data.model.InspectResponse
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object PdfGenerator {

    private const val PAGE_WIDTH = 595
    private const val PAGE_HEIGHT = 842
    private const val MARGIN = 36f
    private const val CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

    fun createInspectionActPdf(
        context: Context,
        equipment: EquipmentDto,
        inspection: InspectResponse,
        frameJpeg: ByteArray?
    ): Uri {
        val document = PdfDocument()
        var pageNumber = 1
        var page = document.startPage(PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, pageNumber).create())
        var canvas = page.canvas
        var y = 0f

        val headerPaint = Paint().apply { color = Color.parseColor("#0E3462") }
        val headerTitlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 18f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        val headerSubPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#D6E4F5")
            textSize = 11f
        }
        val sectionPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#0E3462")
            textSize = 13f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        val bodyPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#313132")
            textSize = 10.5f
        }
        val mutedPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#5A5E67")
            textSize = 9.5f
        }
        val borderPaint = Paint().apply {
            color = Color.parseColor("#E5E7EA")
            strokeWidth = 1f
            style = Paint.Style.STROKE
        }
        val tableHeaderBgPaint = Paint().apply {
            color = Color.parseColor("#F4F5F8")
            style = Paint.Style.FILL
        }

        fun ensureSpace(neededHeight: Float) {
            if (y + neededHeight > PAGE_HEIGHT - MARGIN) {
                document.finishPage(page)
                pageNumber += 1
                page = document.startPage(
                    PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, pageNumber).create()
                )
                canvas = page.canvas
                y = MARGIN
            }
        }

        // Шапка акта
        canvas.drawRect(0f, 0f, PAGE_WIDTH.toFloat(), 76f, headerPaint)
        canvas.drawText("ПромСкан · КСТ Энерго", MARGIN, 32f, headerTitlePaint)
        val dateStr = SimpleDateFormat("dd.MM.yyyy HH:mm", Locale("ru")).format(Date())
        canvas.drawText("Акт осмотра оборудования · $dateStr", MARGIN, 54f, headerSubPaint)
        y = 98f

        // Данные оборудования
        canvas.drawText("Оборудование", MARGIN, y, sectionPaint)
        y += 16f
        val eqLines = listOf(
            "Название: ${equipment.name ?: equipment.id ?: "—"}",
            "ID: ${equipment.id ?: "—"}   Инв. №: ${equipment.inventoryNumber ?: "—"}",
            "Расположение: ${equipment.location ?: "—"}   Состояние: ${Formatters.equipmentStateLabel(equipment.state)}",
            "Последнее ТО: ${Formatters.formatDateShort(equipment.lastMaintenanceAt)}   Следующее ТО: ${Formatters.formatDateShort(equipment.nextMaintenanceAt)}"
        )
        eqLines.forEach { line ->
            y = drawWrappedText(canvas, line, MARGIN, y, CONTENT_WIDTH, bodyPaint, 14f)
        }
        y += 10f

        // Фото осмотра
        if (frameJpeg != null) {
            val bitmap = BitmapFactory.decodeByteArray(frameJpeg, 0, frameJpeg.size)
            if (bitmap != null) {
                val maxPhotoW = 240f
                val scale = maxPhotoW / bitmap.width.coerceAtLeast(1)
                val photoW = maxPhotoW
                val photoH = (bitmap.height * scale).coerceAtMost(180f)
                ensureSpace(photoH + 28f)
                canvas.drawText("Кадр осмотра", MARGIN, y, sectionPaint)
                y += 10f
                val destRect = Rect(
                    MARGIN.toInt(),
                    y.toInt(),
                    (MARGIN + photoW).toInt(),
                    (y + photoH).toInt()
                )
                canvas.drawBitmap(bitmap, null, destRect, null)
                canvas.drawRect(destRect, borderPaint)
                bitmap.recycle()
                y += photoH + 16f
            }
        }

        // Таблица дефектов
        ensureSpace(44f)
        canvas.drawText("Выявленные дефекты", MARGIN, y, sectionPaint)
        y += 12f

        val defects = inspection.defects.orEmpty()
        if (defects.isEmpty()) {
            y = drawWrappedText(canvas, "Дефекты не обнаружены.", MARGIN, y + 6f, CONTENT_WIDTH, bodyPaint, 14f)
        } else {
            val colWidths = floatArrayOf(28f, 165f, 80f, 85f, CONTENT_WIDTH - 358f)
            val rowHeaderH = 22f
            canvas.drawRect(MARGIN, y, MARGIN + CONTENT_WIDTH, y + rowHeaderH, tableHeaderBgPaint)
            canvas.drawRect(MARGIN, y, MARGIN + CONTENT_WIDTH, y + rowHeaderH, borderPaint)

            val headers = listOf("№", "Дефект", "Уверенность", "Критичность", "Рекомендация")
            var colX = MARGIN + 6f
            headers.forEachIndexed { idx, title ->
                canvas.drawText(title, colX, y + 15f, mutedPaint)
                colX += colWidths[idx]
            }
            y += rowHeaderH

            defects.forEachIndexed { index, defect ->
                val numText = "${index + 1}"
                val labelText = defect.label ?: "Дефект"
                val confText = "${((defect.confidence ?: 0.0) * 100).toInt()}%"
                val sevText = Formatters.severityLabel(defect.severity)
                val recText = defect.recommendation ?: "—"

                val recLines = wrapText(recText, colWidths[4] - 10f, bodyPaint)
                val labelLines = wrapText(labelText, colWidths[1] - 10f, bodyPaint)
                val maxLines = maxOf(recLines.size, labelLines.size, 1)
                val rowH = maxLines * 13f + 10f

                ensureSpace(rowH)
                canvas.drawRect(MARGIN, y, MARGIN + CONTENT_WIDTH, y + rowH, borderPaint)

                var cx = MARGIN + 6f
                canvas.drawText(numText, cx, y + 15f, bodyPaint)
                cx += colWidths[0]

                labelLines.forEachIndexed { lIdx, textLine ->
                    canvas.drawText(textLine, cx, y + 15f + lIdx * 13f, bodyPaint)
                }
                cx += colWidths[1]

                canvas.drawText(confText, cx, y + 15f, bodyPaint)
                cx += colWidths[2]

                canvas.drawText(sevText, cx, y + 15f, bodyPaint)
                cx += colWidths[3]

                recLines.forEachIndexed { lIdx, textLine ->
                    canvas.drawText(textLine, cx, y + 15f + lIdx * 13f, bodyPaint)
                }
                y += rowH
            }
        }

        y += 16f

        // Заключение и параметры состояния
        ensureSpace(48f)
        canvas.drawText("Заключение", MARGIN, y, sectionPaint)
        y += 15f

        val params = inspection.conditionParameters
        if (params != null) {
            val paramLine = "Утечка масла: ${Formatters.percent(params.oilLeakProbability)}   " +
                "Ржавчина: ${Formatters.percent(params.rustProbability)}   " +
                "Плохой сварной шов: ${Formatters.percent(params.poorWeldProbability)}"
            y = drawWrappedText(canvas, paramLine, MARGIN, y, CONTENT_WIDTH, mutedPaint, 14f)
            y += 4f
        }

        val summary = inspection.summary.orEmpty().ifBlank { "Сводка отсутствует." }
        y = drawWrappedText(canvas, summary, MARGIN, y, CONTENT_WIDTH, bodyPaint, 14f)

        val probableCause = inspection.llm?.probableCause
        if (!probableCause.isNullOrBlank()) {
            y += 6f
            ensureSpace(28f)
            y = drawWrappedText(canvas, "Вероятная причина: $probableCause", MARGIN, y, CONTENT_WIDTH, bodyPaint, 14f)
        }

        val steps = inspection.llm?.recommendationSteps.orEmpty()
        if (steps.isNotEmpty()) {
            y += 8f
            ensureSpace(26f)
            canvas.drawText("Рекомендации", MARGIN, y, sectionPaint)
            y += 15f
            steps.forEachIndexed { idx, step ->
                ensureSpace(20f)
                y = drawWrappedText(canvas, "${idx + 1}. $step", MARGIN, y, CONTENT_WIDTH, bodyPaint, 14f)
            }
        }

        document.finishPage(page)

        val actsDir = File(context.cacheDir, "acts").apply { mkdirs() }
        val fileName = "promscan_act_${System.currentTimeMillis()}.pdf"
        val outFile = File(actsDir, fileName)
        FileOutputStream(outFile).use { fos ->
            document.writeTo(fos)
        }
        document.close()

        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            outFile
        )
    }

    private fun drawWrappedText(
        canvas: Canvas,
        text: String,
        x: Float,
        startY: Float,
        maxWidth: Float,
        paint: Paint,
        lineHeight: Float
    ): Float {
        var curY = startY
        val lines = wrapText(text, maxWidth, paint)
        lines.forEach { line ->
            canvas.drawText(line, x, curY, paint)
            curY += lineHeight
        }
        return curY
    }

    private fun wrapText(text: String, maxWidth: Float, paint: Paint): List<String> {
        if (text.isBlank()) return listOf("")
        val result = mutableListOf<String>()
        val paragraphs = text.split('\n')
        for (paragraph in paragraphs) {
            val words = paragraph.split(' ')
            var current = StringBuilder()
            for (word in words) {
                val candidate = if (current.isEmpty()) word else "$current $word"
                if (paint.measureText(candidate) <= maxWidth) {
                    current = StringBuilder(candidate)
                } else {
                    if (current.isNotEmpty()) {
                        result.add(current.toString())
                    }
                    current = StringBuilder(word)
                }
            }
            if (current.isNotEmpty()) {
                result.add(current.toString())
            }
        }
        return if (result.isEmpty()) listOf("") else result
    }
}
