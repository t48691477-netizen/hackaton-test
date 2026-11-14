package ru.cyber102.arinspector.util

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

object Formatters {
    private val dateTimeOut = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")
    private val dateOut = DateTimeFormatter.ofPattern("dd.MM.yyyy")

    fun formatDateTime(raw: String?): String {
        if (raw.isNullOrBlank()) return "—"
        return try {
            val instant = Instant.parse(raw)
            dateTimeOut.format(instant.atZone(ZoneId.systemDefault()))
        } catch (_: Exception) {
            try {
                val localDate = LocalDate.parse(raw.take(10))
                dateOut.format(localDate)
            } catch (_: Exception) {
                raw
            }
        }
    }

    fun formatDateShort(raw: String?): String {
        if (raw.isNullOrBlank()) return "—"
        return try {
            val localDate = LocalDate.parse(raw.take(10))
            dateOut.format(localDate)
        } catch (_: Exception) {
            raw
        }
    }

    fun percent(value: Double?): String {
        val pct = ((value ?: 0.0).coerceIn(0.0, 1.0) * 100.0).roundToInt()
        return "$pct%"
    }

    fun roleLabel(role: String?): String = when (role?.lowercase()) {
        "director" -> "Директор"
        "admin" -> "Администратор"
        "dispatcher" -> "Диспетчер"
        "engineer" -> "Инженер"
        else -> role?.takeIf { it.isNotBlank() } ?: "Сотрудник"
    }

    fun equipmentStateLabel(state: String?): String = when (state?.lowercase()) {
        "operational" -> "В работе"
        "maintenance" -> "Обслуживание"
        "fault" -> "Неисправность"
        else -> state?.takeIf { it.isNotBlank() } ?: "Неизвестно"
    }

    fun severityLabel(severity: String?): String = when (severity?.lowercase()) {
        "high" -> "высокая"
        "medium" -> "средняя"
        "low" -> "низкая"
        else -> "средняя"
    }

    fun reportStatusLabel(status: String?): String = when (status?.lowercase()) {
        "open" -> "Открыта"
        "in_progress" -> "В работе"
        "closed" -> "Закрыта"
        else -> status?.takeIf { it.isNotBlank() } ?: "—"
    }
}
